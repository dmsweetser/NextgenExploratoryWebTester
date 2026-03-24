// Main JavaScript for the web testing bot application

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Auto-refresh for bot status
    if (document.querySelector('.timeline')) {
        setTimeout(function() {
            window.location.reload();
        }, 5000);
    }
});

// Function to handle form submissions
document.querySelectorAll('form').forEach(function(form) {
    form.addEventListener('submit', function(e) {
        // Add loading state
        var submitBtn = form.querySelector('[type="submit"]');
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = submitBtn.innerHTML + ' <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>';
        }
    });
});

// Self-test modal
document.addEventListener('DOMContentLoaded', function() {
    var selfTestModal = document.getElementById('selfTestModal');
    if (selfTestModal) {
        selfTestModal.addEventListener('show.bs.modal', function () {
            console.log('Self-test modal shown');
        });
    }
});
