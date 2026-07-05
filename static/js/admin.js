// Admin panel enhancements — confirmation prompts + tooltips.
// (This file previously didn't exist at all; the template referenced it
// but the browser was always getting a 404 for it.)

document.addEventListener('DOMContentLoaded', function () {
    // Confirm before any destructive action button/link
    document.querySelectorAll('[data-confirm]').forEach(function (el) {
        el.addEventListener('click', function (e) {
            const message = el.getAttribute('data-confirm') || 'Are you sure?';
            if (!window.confirm(message)) {
                e.preventDefault();
                e.stopPropagation();
            }
        });
    });

    // Enable Bootstrap tooltips if any are present
    document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (el) {
        if (window.bootstrap) {
            new bootstrap.Tooltip(el);
        }
    });

    // Auto-dismiss flash alerts after a few seconds
    document.querySelectorAll('.alert-dismissible').forEach(function (alert) {
        setTimeout(function () {
            if (window.bootstrap) {
                const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
                bsAlert.close();
            }
        }, 6000);
    });
});
