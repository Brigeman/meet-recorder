from winrec.gui.cooldown import CooldownManager


def test_app_level_dismiss_blocks_other_context_keys():
    cm = CooldownManager(90, 120)
    cm.record_dismiss("teams:ctx:1", app="Microsoft Teams")
    assert not cm.can_prompt("teams:ctx:2", app="Microsoft Teams")
    assert cm.can_prompt("zoom:ctx:1", app="Zoom")


def test_app_level_post_stop_blocks_other_context_keys():
    cm = CooldownManager(90, 120)
    cm.record_post_stop("teams:ctx:1", app="Microsoft Teams")
    assert not cm.can_prompt("teams:ctx:3", app="Microsoft Teams")
    assert cm.can_prompt("edge:ctx:3", app="Microsoft Edge")
