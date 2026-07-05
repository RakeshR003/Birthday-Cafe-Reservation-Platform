// Enhanced Main JavaScript for Birthday Cafe Reservations

document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

function initializeApp() {
    // Initialize components
    initializeBackToTop();
    initializeAnimations();
    initializeTooltips();
    enhanceForms();
    enableSmoothScrolling();
    enableLazyLoading();
    enableButtonLoading();
    initializeCounters();
    initializeParallax();
}

function initializeBackToTop() {
    const backToTop = document.getElementById('backToTop');
    
    window.addEventListener('scroll', function() {
        if (window.pageYOffset > 300) {
            backToTop.classList.add('show');
        } else {
            backToTop.classList.remove('show');
        }
    });
    
    backToTop.addEventListener('click', function(e) {
        e.preventDefault();
        window.scrollTo({
            top: 0,
            behavior: 'smooth'
        });
    });
}

function initializeAnimations() {
    // Initialize AOS if available
    if (typeof AOS !== 'undefined') {
        AOS.init({
            duration: 800,
            easing: 'ease-in-out',
            once: true,
            offset: 100
        });
    }
    
    // Add floating animation to elements with .floating class
    document.querySelectorAll('.floating').forEach(el => {
        el.style.animationDelay = Math.random() * 2 + 's';
    });
}

function initializeTooltips() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    const tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

function enhanceForms() {
    // Add real-time validation feedback
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        const inputs = form.querySelectorAll('input, select, textarea');
        
        inputs.forEach(input => {
            input.addEventListener('blur', function() {
                validateField(this);
            });
            
            input.addEventListener('input', function() {
                if (this.classList.contains('is-invalid')) {
                    validateField(this);
                }
            });
        });
        
        // Add character counters for textareas
        form.querySelectorAll('textarea').forEach(textarea => {
            const maxLength = textarea.getAttribute('maxlength');
            if (maxLength) {
                addCharacterCounter(textarea, maxLength);
            }
        });
    });
}

function addCharacterCounter(textarea, maxLength) {
    const counter = document.createElement('div');
    counter.className = 'form-text text-end character-counter';
    counter.textContent = `0/${maxLength}`;
    
    textarea.parentNode.appendChild(counter);
    
    textarea.addEventListener('input', function() {
        const currentLength = this.value.length;
        counter.textContent = `${currentLength}/${maxLength}`;
        
        if (currentLength > maxLength * 0.8) {
            counter.classList.add('text-warning');
        } else {
            counter.classList.remove('text-warning');
        }
        
        if (currentLength > maxLength) {
            counter.classList.add('text-danger');
        } else {
            counter.classList.remove('text-danger');
        }
    });
}

function validateField(field) {
    if (field.checkValidity()) {
        field.classList.remove('is-invalid');
        field.classList.add('is-valid');
    } else {
        field.classList.remove('is-valid');
        field.classList.add('is-invalid');
    }
}

function enableSmoothScrolling() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            const href = this.getAttribute('href');
            if (href !== '#') {
                e.preventDefault();
                const target = document.querySelector(href);
                if (target) {
                    const offsetTop = target.getBoundingClientRect().top + window.pageYOffset - 80;
                    window.scrollTo({
                        top: offsetTop,
                        behavior: 'smooth'
                    });
                }
            }
        });
    });
}

function enableLazyLoading() {
    if ('IntersectionObserver' in window) {
        const lazyImageObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const lazyImage = entry.target;
                    lazyImage.src = lazyImage.dataset.src;
                    lazyImage.classList.remove('lazy');
                    lazyImageObserver.unobserve(lazyImage);
                }
            });
        });

        document.querySelectorAll('img.lazy').forEach(lazyImage => {
            lazyImageObserver.observe(lazyImage);
        });
    }
}

function enableButtonLoading() {
    document.addEventListener('submit', function(e) {
        const form = e.target;
        const submitBtn = form.querySelector('button[type="submit"], input[type="submit"]');
        
        if (submitBtn && !submitBtn.disabled) {
            const originalText = submitBtn.innerHTML;
            submitBtn.innerHTML = `
                <span class="spinner-border spinner-border-sm me-2" role="status"></span>
                Processing...
            `;
            submitBtn.disabled = true;
            
            // Re-enable button if form submission fails
            setTimeout(() => {
                if (submitBtn.disabled) {
                    submitBtn.innerHTML = originalText;
                    submitBtn.disabled = false;
                }
            }, 10000);
        }
    });
}

function initializeCounters() {
    // Animated number counters for stats
    const counters = document.querySelectorAll('.counter');
    
    counters.forEach(counter => {
        const target = +counter.getAttribute('data-target');
        const duration = 2000; // 2 seconds
        const step = target / (duration / 16); // 60fps
        
        let current = 0;
        
        const updateCounter = () => {
            current += step;
            if (current < target) {
                counter.textContent = Math.ceil(current).toLocaleString();
                requestAnimationFrame(updateCounter);
            } else {
                counter.textContent = target.toLocaleString();
            }
        };
        
        // Start counter when element is in viewport
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    updateCounter();
                    observer.unobserve(entry.target);
                }
            });
        });
        
        observer.observe(counter);
    });
}

function initializeParallax() {
    // Simple parallax effect for hero section
    const hero = document.querySelector('.hero-section');
    if (hero) {
        window.addEventListener('scroll', function() {
            const scrolled = window.pageYOffset;
            const rate = scrolled * -0.5;
            hero.style.transform = `translateY(${rate}px)`;
        });
    }
}

// Utility functions
function formatPhoneNumber(input) {
    let phone = input.value.replace(/\D/g, '');
    
    if (phone.length <= 3) {
        input.value = phone;
    } else if (phone.length <= 6) {
        input.value = '(' + phone.slice(0, 3) + ') ' + phone.slice(3);
    } else {
        input.value = '(' + phone.slice(0, 3) + ') ' + phone.slice(3, 6) + '-' + phone.slice(6, 10);
    }
}

function isFutureDate(dateString) {
    const inputDate = new Date(dateString);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return inputDate >= today;
}

function getMinBookingDate() {
    const today = new Date();
    today.setDate(today.getDate() + 1); // Minimum 1 day in advance
    return today.toISOString().split('T')[0];
}

// API helper functions
async function apiCall(endpoint, options = {}) {
    try {
        const response = await fetch(endpoint, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.message || 'API request failed');
        }
        
        return data;
    } catch (error) {
        console.error('API call failed:', error);
        showNotification('An error occurred. Please try again.', 'error');
        return { success: false, error: error.message };
    }
}

function showNotification(message, type = 'info', duration = 5000) {
    // Remove existing notifications
    const existingAlerts = document.querySelectorAll('.alert-dismissible');
    existingAlerts.forEach(alert => {
        if (!alert.classList.contains('permanent')) {
            alert.remove();
        }
    });
    
    // Create new notification
    const alert = document.createElement('div');
    alert.className = `alert alert-${type === 'error' ? 'danger' : type} alert-dismissible fade show`;
    alert.innerHTML = `
        <div class="d-flex align-items-center">
            <i class="bi bi-${getNotificationIcon(type)} me-2"></i>
            <div>${message}</div>
        </div>
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    // Add to page
    const container = document.querySelector('.container') || document.body;
    container.insertBefore(alert, container.firstChild);
    
    // Auto-remove after duration
    if (duration > 0) {
        setTimeout(() => {
            if (alert.parentNode) {
                const bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            }
        }, duration);
    }
}

function getNotificationIcon(type) {
    const icons = {
        'success': 'check-circle-fill',
        'error': 'exclamation-triangle-fill',
        'warning': 'exclamation-triangle-fill',
        'info': 'info-circle-fill'
    };
    return icons[type] || 'info-circle-fill';
}

// Utility function to format currency
function formatCurrency(amount, currency = 'INR') {
    return new Intl.NumberFormat('en-IN', {
        style: 'currency',
        currency: currency,
        minimumFractionDigits: 0,
        maximumFractionDigits: 0
    }).format(amount);
}

// Debounce function for performance
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Export functions for global use
window.BirthdayCafe = {
    formatCurrency,
    showNotification,
    apiCall,
    debounce
};

// Add some fun confetti effect for successful bookings
function showConfetti() {
    const confettiCount = 200;
    const confettiColors = ['#ff0000', '#00ff00', '#0000ff', '#ffff00', '#ff00ff', '#00ffff'];
    
    for (let i = 0; i < confettiCount; i++) {
        const confetti = document.createElement('div');
        confetti.className = 'confetti';
        confetti.style.cssText = `
            position: fixed;
            width: 10px;
            height: 10px;
            background: ${confettiColors[Math.floor(Math.random() * confettiColors.length)]};
            top: -10px;
            left: ${Math.random() * 100}vw;
            opacity: ${Math.random() + 0.5};
            transform: rotate(${Math.random() * 360}deg);
            pointer-events: none;
            z-index: 9999;
        `;
        
        document.body.appendChild(confetti);
        
        const animation = confetti.animate([
            { transform: `translateY(0) rotate(0deg)`, opacity: 1 },
            { transform: `translateY(${window.innerHeight}px) rotate(${Math.random() * 360}deg)`, opacity: 0 }
        ], {
            duration: Math.random() * 3000 + 2000,
            easing: 'cubic-bezier(0.1, 0.8, 0.2, 1)'
        });
        
        animation.onfinish = () => confetti.remove();
    }
}

// Add confetti to booking confirmation
document.addEventListener('DOMContentLoaded', function() {
    if (window.location.pathname.includes('booking-confirm')) {
        setTimeout(showConfetti, 500);
    }
});