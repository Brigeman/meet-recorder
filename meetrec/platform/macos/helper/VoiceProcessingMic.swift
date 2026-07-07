import AVFoundation
import Foundation

// MeetRecVoiceMic
//
// Captures the microphone through Apple's Voice Processing I/O audio unit
// (AVAudioEngine inputNode.setVoiceProcessingEnabled), which performs
// hardware/OS-grade acoustic echo cancellation using the system audio output as
// the echo reference, plus noise suppression and AGC. The echo-cancelled mic is
// converted to the recorder's PCM contract and streamed on stdout.
//
// Contract with the Python recorder (identical framing style to
// MeetRecSystemAudio, but MONO): 16-bit signed PCM, 48 kHz, 1 channel.
// A single ready line "READY voiceio\n" is written to stderr once the engine has
// started so the Python side can confirm the native path initialised; any fatal
// error is written to stderr and the process exits non-zero so Python can fall
// back to the plain sounddevice mic + export-time hard-gate.
final class VoiceProcessingMic {
    private let engine = AVAudioEngine()
    private let stdoutHandle = FileHandle.standardOutput
    private let targetRate: Double = 48000
    private var converter: AVAudioConverter?
    private var inputFormat: AVAudioFormat?

    private lazy var outputFormat = AVAudioFormat(
        commonFormat: .pcmFormatInt16,
        sampleRate: targetRate,
        channels: 1,
        interleaved: true
    )!

    func start() throws {
        let input = engine.inputNode

        // Must be enabled before the engine starts. This swaps the plain HAL I/O
        // unit for kAudioUnitSubType_VoiceProcessingIO, whose AEC references the
        // current system output (the meeting app's playback on the speakers).
        try input.setVoiceProcessingEnabled(true)

        let inFormat = input.outputFormat(forBus: 0)
        guard inFormat.sampleRate > 0, inFormat.channelCount > 0 else {
            throw NSError(
                domain: "MeetRecVoiceMic", code: 3,
                userInfo: [NSLocalizedDescriptionKey: "invalid input format \(inFormat)"]
            )
        }
        inputFormat = inFormat
        converter = AVAudioConverter(from: inFormat, to: outputFormat)

        // We deliberately do NOT connect the mic to the output node to avoid
        // feedback; the VPIO reference is the system render mix, handled by the OS.
        input.installTap(onBus: 0, bufferSize: 2048, format: inFormat) { [weak self] buffer, _ in
            self?.handle(buffer)
        }

        engine.prepare()
        try engine.start()
        FileHandle.standardError.write(Data("READY voiceio rate=\(Int(inFormat.sampleRate)) ch=\(inFormat.channelCount)\n".utf8))
    }

    private func handle(_ inBuffer: AVAudioPCMBuffer) {
        guard let converter, let inFormat = inputFormat else { return }
        let frameCount = inBuffer.frameLength
        guard frameCount > 0 else { return }

        let capacity = AVAudioFrameCount(
            (Double(frameCount) * targetRate / inFormat.sampleRate).rounded(.up)
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
        stdoutHandle.write(Data(bytes: channelData[0], count: byteCount))
    }
}

if #available(macOS 10.15, *) {
    let mic = VoiceProcessingMic()
    do {
        try mic.start()
    } catch {
        FileHandle.standardError.write(Data("error: \(error)\n".utf8))
        exit(1)
    }
    RunLoop.main.run()
} else {
    FileHandle.standardError.write(Data("error: macOS 10.15+ required\n".utf8))
    exit(2)
}
