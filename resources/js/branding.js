(function() {
    try {
        Object.defineProperty(navigator, 'vendor', {
            get: () => 'ospab foundation',
            configurable: true,
            enumerable: true
        });
        Object.defineProperty(navigator, 'appCodeName', {
            get: () => 'Surf',
            configurable: true,
            enumerable: true
        });
        Object.defineProperty(navigator, 'appName', {
            get: () => 'Surf Browser',
            configurable: true,
            enumerable: true
        });
        Object.defineProperty(navigator, 'product', {
            get: () => 'SurfEngine',
            configurable: true,
            enumerable: true
        });
    } catch (e) {}

    try {
        document.addEventListener('click', function(e) {
            var a = e.target && e.target.closest ? e.target.closest('a') : null;
            if (!a || !a.href) return;
            if (e.ctrlKey || e.metaKey || e.button === 1) {
                e.preventDefault();
                e.stopPropagation();
                window.open(a.href, '_blank');
            }
        }, true);
    } catch (e) {}
})();
