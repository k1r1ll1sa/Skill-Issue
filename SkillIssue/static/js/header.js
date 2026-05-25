(function () {
    const header = document.getElementById('header');
    const menuBtn = document.getElementById('header-menu-btn');
    const overlay = document.getElementById('header-overlay');

    if (!header || !menuBtn) {
        return;
    }

    const MOBILE_BREAKPOINT = 1023;

    function isMobile() {
        return window.matchMedia('(max-width: ' + MOBILE_BREAKPOINT + 'px)').matches;
    }

    function setMenuOpen(open) {
        header.classList.toggle('menu-open', open);
        menuBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
        document.body.classList.toggle('header-menu-open', open);

        if (overlay) {
            overlay.hidden = !open;
        }
    }

    function closeMenu() {
        setMenuOpen(false);
    }

    function toggleMenu() {
        if (!isMobile()) {
            return;
        }
        setMenuOpen(!header.classList.contains('menu-open'));
    }

    menuBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        toggleMenu();
    });

    if (overlay) {
        overlay.addEventListener('click', closeMenu);
    }

    header.querySelectorAll('.header-nav a').forEach(function (link) {
        link.addEventListener('click', function () {
            if (isMobile()) {
                closeMenu();
            }
        });
    });

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
            closeMenu();
        }
    });

    window.addEventListener('resize', function () {
        if (!isMobile()) {
            closeMenu();
        }
    });
})();
