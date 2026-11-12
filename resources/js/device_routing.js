(function() {
    if (window.__surf_device_routing_installed) return;
    window.__surf_device_routing_installed = true;

    window.__surf_media_config = window.__surf_media_config || {
        allow_audio: true,
        selected_audio: "",
        allow_video: true,
        selected_video: ""
    };

    window.__surf_set_media_config = function(cfg) {
        if (!cfg) return;
        window.__surf_media_config = Object.assign(window.__surf_media_config, cfg);
    };

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) return;

    var origGetUserMedia = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
    var origEnumerateDevices = navigator.mediaDevices.enumerateDevices.bind(navigator.mediaDevices);

    async function matchDeviceId(kind, targetName) {
        if (!targetName) return null;
        try {
            var devices = await origEnumerateDevices();
            var targetLower = targetName.toLowerCase();
            for (var i = 0; i < devices.length; i++) {
                var d = devices[i];
                if (d.kind === kind && d.label && d.label.toLowerCase() === targetLower) {
                    return d.deviceId;
                }
            }
            for (var i = 0; i < devices.length; i++) {
                var d = devices[i];
                if (d.kind === kind && d.label && (d.label.toLowerCase().includes(targetLower) || targetLower.includes(d.label.toLowerCase()))) {
                    return d.deviceId;
                }
            }
        } catch (e) {}
        return null;
    }

    navigator.mediaDevices.getUserMedia = async function(constraints) {
        var cfg = window.__surf_media_config || {};
        var c = constraints ? Object.assign({}, constraints) : {};

        if (c.audio) {
            if (cfg.allow_audio === false) {
                delete c.audio;
            } else if (cfg.selected_audio) {
                var devId = await matchDeviceId('audioinput', cfg.selected_audio);
                if (devId) {
                    if (typeof c.audio === 'object') {
                        c.audio = Object.assign({}, c.audio, { deviceId: { exact: devId } });
                    } else {
                        c.audio = { deviceId: { exact: devId } };
                    }
                }
            }
        }

        if (c.video) {
            if (cfg.allow_video === false) {
                delete c.video;
            } else if (cfg.selected_video) {
                var devId = await matchDeviceId('videoinput', cfg.selected_video);
                if (devId) {
                    if (typeof c.video === 'object') {
                        c.video = Object.assign({}, c.video, { deviceId: { exact: devId } });
                    } else {
                        c.video = { deviceId: { exact: devId } };
                    }
                }
            }
        }

        if (!c.audio && !c.video) {
            var err = new Error('Permission denied: audio and video are disabled in surf');
            err.name = 'NotAllowedError';
            throw err;
        }

        return origGetUserMedia(c);
    };
})();
