// Main JavaScript for the web testing bot application

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Auto-refresh for bot status via AJAX
    if (document.querySelector('.timeline')) {
        setInterval(function() {
            const botId = window.location.pathname.split('/').pop();
            fetch(`/bot/${botId}`)
                .then(response => response.text())
                .then(html => {
                    const parser = new DOMParser();
                    const doc = parser.parseFromString(html, 'text/html');
                    const newContent = doc.querySelector('.timeline').innerHTML;
                    document.querySelector('.timeline').innerHTML = newContent;
                })
                .catch(error => console.error('Error refreshing content:', error));
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

// Restore scroll position on page load
if (localStorage.getItem('scrollPosition')) {
    setTimeout(function() {
        var mainContent = document.getElementById('mainContent');
        if (mainContent) {
            mainContent.scrollTop = parseInt(localStorage.getItem('scrollPosition'));
            localStorage.removeItem('scrollPosition');
        }
    }, 100);
}

// Save scroll position before unload (if not completed)
window.addEventListener('beforeunload', function() {
    if (!document.getElementById('testCompleteAlert')) {
        var mainContent = document.getElementById('mainContent');
        if (mainContent) {
            localStorage.setItem('scrollPosition', mainContent.scrollTop);
        }
    }
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

// Function to show full-size image
function showFullImage(src) {
    const fullImage = document.getElementById('fullImage');
    const screenshotFull = document.getElementById('screenshotFull');

    if (fullImage && screenshotFull) {
        fullImage.src = src;
        screenshotFull.style.display = 'flex';
    }
}

// Function to close full-size image
function closeFullImage() {
    const screenshotFull = document.getElementById('screenshotFull');
    if (screenshotFull) {
        screenshotFull.style.display = 'none';
    }
}
