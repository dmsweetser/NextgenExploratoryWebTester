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

// Function to show large image in modal
function showLargeImage(imageUrl) {
    // Create modal if it doesn't exist
    let modal = document.getElementById('imageModal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'imageModal';
        modal.className = 'modal fade';
        modal.tabIndex = '-1';
        modal.setAttribute('aria-labelledby', 'imageModalLabel');
        modal.setAttribute('aria-hidden', 'true');

        modal.innerHTML = `
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title" id="imageModalLabel">Full Screenshot</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body">
                        <img id="largeImage" src="" class="img-fluid" alt="Full screenshot">
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
    }

    // Set the image source
    let img = document.getElementById('largeImage');
    if (img) {
        img.src = imageUrl;
    }

    // Show the modal
    let modalInstance = bootstrap.Modal.getInstance(modal) || new bootstrap.Modal(modal);
    modalInstance.show();
}
