from types import SimpleNamespace as NS
import pytest
from app.services.camera_guidance import camera_guidance


def face(bbox=(200, 100, 440, 380), quality=True, live=True):
    return NS(bbox=bbox, quality=NS(passed=quality, errors=[]),
              liveness=NS(is_real=live) if live is not None else None)


def test_centered_good_capture_is_ready_but_not_authorized():
    result = camera_guidance(face(), 640, 480)
    assert result['accepted']
    assert 'access_decision' not in result


@pytest.mark.parametrize('feature', [None, face((10, 10, 100, 100)), face((150, 5, 500, 475)),
                                   face((0, 100, 180, 380)), face(quality=False), face(live=False),
                                   face(live=None), face((float('nan'), 0, 440, 380))])
def test_unsafe_or_poorly_positioned_capture_is_not_ready(feature):
    assert not camera_guidance(feature, 640, 480)['accepted']


def test_portrait_camera_coordinates_are_normalized():
    assert camera_guidance(face((140, 130, 340, 510)), 480, 640)['accepted']
