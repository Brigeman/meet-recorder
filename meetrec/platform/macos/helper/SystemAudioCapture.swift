import AVFoundation
import CoreMedia
import Foundation
import ScreenCaptureKit

@available(macOS 13.0, *)
final class SystemAudioCapture: NSObject, SCStreamDelegate, SCStreamOutput {
    private let stdout = FileHandle.standardOutput
    private var stream: SCStream?
    private let sampleRate: Double = 48000

    // Contract with the Python recorder: 16-bit signed PCM, 48 kHz, 2 channels,
    // interleaved (L,R,L,R...). ScreenCaptureKit delivers Float32 (often
    // non-interleaved) audio, so we must convert rather than dump raw bytes.
    private lazy var outputFormat = AVAudioFormat(
        commonFormat: .pcmFormatInt16,
        sampleRate: sampleRate,
        channels: 2,
        interleaved: true
    )!
    private var converter: AVAudioConverter?
    private var inputFormat: AVAudioFormat?

    func start() async throws {
        let content = try await SCShareableContent.excludingDesktopWindows(false, onScreenWindowsOnly: true)
        guard let display = content.displays.first else {
            throw NSError(domain: "MeetRecSystemAudio", code: 1, userInfo: [NSLocalizedDescriptionKey: "No display"])
        }

        let filter = SCContentFilter(display: display, excludingWindows: [])
        let config = SCStreamConfiguration()
        config.capturesAudio = true
        config.sampleRate = Int(sampleRate)
        config.channelCount = 2
        config.width = 2
        config.height = 2
        config.minimumFrameInterval = CMTime(value: 1, timescale: 1)
        config.showsCursor = false

        let stream = SCStream(filter: filter, configuration: config, delegate: self)
        try stream.addStreamOutput(self, type: .audio, sampleHandlerQueue: DispatchQueue(label: "meetrec.system-audio"))
        self.stream = stream
        try await stream.startCapture()
    }

    func stream(_ stream: SCStream, didOutputSampleBuffer sampleBuffer: CMSampleBuffer, of type: SCStreamOutputType) {
        guard type == .audio else { return }
        guard sampleBuffer.isValid else { return }
        guard let formatDesc = sampleBuffer.formatDescription else { return }
        guard var asbd = formatDesc.audioStreamBasicDescription else { return }

        guard let inFormat = AVAudioFormat(streamDescription: &asbd) else { return }
        if converter == nil || inputFormat != inFormat {
            converter = AVAudioConverter(from: inFormat, to: outputFormat)
            inputFormat = inFormat
        }
        guard let converter else { return }

        let frameCount = AVAudioFrameCount(CMSampleBufferGetNumSamples(sampleBuffer))
        guard frameCount > 0 else { return }
        guard let inBuffer = AVAudioPCMBuffer(pcmFormat: inFormat, frameCapacity: frameCount) else { return }
        inBuffer.frameLength = frameCount

        let copyStatus = CMSampleBufferCopyPCMDataIntoAudioBufferList(
            sampleBuffer,
            at: 0,
            frameCount: Int32(frameCount),
            into: inBuffer.mutableAudioBufferList
        )
        guard copyStatus == noErr else { return }

        let capacity = AVAudioFrameCount(
            (Double(frameCount) * outputFormat.sampleRate / inFormat.sampleRate).rounded(.up)
        ) + 1
        guard let outBuffer = AVAudioPCMBuffer(pcmFormat: outputFormat, frameCapacity: capacity) else { return }

        var fed = false
        var convError: NSError?
        let status = converter.convert(to: outBuffer, error: &convError) { _, outStatus in
            if fed {
                outStatus.pointee = .noDataNow
                return nil
            }
            fed = true
            outStatus.pointee = .haveData
            return inBuffer
        }

        if status == .error {
            if let convError {
                FileHandle.standardError.write(Data("convert error: \(convError)\n".utf8))
            }
            return
        }

        guard outBuffer.frameLength > 0, let channelData = outBuffer.int16ChannelData else { return }
        let byteCount = Int(outBuffer.frameLength) * Int(outputFormat.streamDescription.pointee.mBytesPerFrame)
        let data = Data(bytes: channelData[0], count: byteCount)
        stdout.write(data)
    }
}

if #available(macOS 13.0, *) {
    let capture = SystemAudioCapture()
    let group = DispatchGroup()
    group.enter()
    Task {
        do {
            try await capture.start()
        } catch {
            FileHandle.standardError.write(Data("error: \(error)\n".utf8))
            exit(1)
        }
        group.leave()
    }
    group.wait()
    RunLoop.main.run()
} else {
    FileHandle.standardError.write(Data("error: macOS 13+ required\n".utf8))
    exit(2)
}
