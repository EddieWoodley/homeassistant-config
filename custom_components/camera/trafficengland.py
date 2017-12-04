"""
Support for Traffic England Cameras. Based on the Generic camera platform.

For more details about this platform, please refer to the documentation at
https://github.com/EddieWoodley.homeassistant-config
"""
import asyncio
import logging
import time

import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant.const import (
    CONF_NAME )
from homeassistant.exceptions import TemplateError
from homeassistant.components.camera import (
    PLATFORM_SCHEMA, Camera)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import config_validation as cv
from homeassistant.util.async import run_coroutine_threadsafe

_LOGGER = logging.getLogger(__name__)

CONF_CAMERA_ID = 'camera_id'
CONF_MIN_FETCH_INTERVAL = 'min_fetch_interval'

DEFAULT_NAME = 'Traffic Camera'

CAMERA_URL = 'http://public.highwaystrafficcameras.co.uk/cctvpublicaccess/images/{}.jpg'
REFERER_URL = 'http://public.highwaystrafficcameras.co.uk/cctvpublicaccess/html/{}.html'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_CAMERA_ID): cv.template,
    vol.Optional(CONF_MIN_FETCH_INTERVAL, default=30): cv.positive_int,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


@asyncio.coroutine
# pylint: disable=unused-argument
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up a Traffic England Camera."""
    async_add_devices([TrafficEnglandCamera(hass, config)])


class TrafficEnglandCamera(Camera):
    """Am implementation of a Traffic England camera."""

    def __init__(self, hass, device_info):
        """Initialize a Traffic England camera."""
        super().__init__()
        self.hass = hass
        self._name = device_info.get(CONF_NAME)
        self._camera_id = device_info[CONF_CAMERA_ID]
        self._camera_id.hass = hass
        self._min_fetch_interval = device_info[CONF_MIN_FETCH_INTERVAL]
        self._last_image = None
        self._last_time = 0

    def camera_image(self):
        """Return bytes of camera image."""
        return run_coroutine_threadsafe(
                self.async_camera_image(), self.hass.loop).result()

    @asyncio.coroutine
    def async_camera_image(self):
        """Return a still image response from the camera."""
        try:
            camera_id = self._camera_id.async_render()
            url = CAMERA_URL.format(camera_id)
        except TemplateError as err:
            _LOGGER.error(
                "Error parsing template %s: %s", self._still_image_url, err)
            return self._last_image

        """Only fetch new image if min_fetch_interval has passed"""
        if time.time() - self._last_time >= self._min_fetch_interval:
            try:
                websession = async_get_clientsession(self.hass)
                with async_timeout.timeout(10, loop=self.hass.loop):
                    response = yield from websession.get(
                        url, headers={'referer': REFERER_URL.format(camera_id)})
                self._last_image = yield from response.read()
                self._last_time = time.time()
            except asyncio.TimeoutError:
                _LOGGER.error("Timeout getting camera image")
            except aiohttp.ClientError as err:
                _LOGGER.error("Error getting new camera image: %s", err)

        return self._last_image

    @property
    def name(self):
        """Return the name of this device."""
        return self._name