/* ============================================================
   Apex Career Institute — Main JavaScript
   Vanilla ES6+. No jQuery. Bootstrap 5 JS loaded via CDN.
   ============================================================ */

(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {

        // ─── Navbar Scroll Effect ───────────────────────────────
        const navbar = document.getElementById('mainNav');
        let ticking = false;

        function handleNavScroll() {
            if (window.scrollY > 50) {
                navbar.classList.add('scrolled');
            } else {
                navbar.classList.remove('scrolled');
            }
            ticking = false;
        }

        window.addEventListener('scroll', function () {
            if (!ticking) {
                requestAnimationFrame(handleNavScroll);
                ticking = true;
            }
        }, { passive: true });

        // Trigger on load in case page is already scrolled
        handleNavScroll();

        // ─── Smooth Scroll for Anchor Links ────────────────────
        const NAVBAR_HEIGHT = 76;
        const offcanvasEl = document.getElementById('navbarOffcanvas');
        let offcanvasInstance = null;
        if (offcanvasEl) {
            offcanvasInstance = bootstrap.Offcanvas.getOrCreateInstance(offcanvasEl);
        }

        document.querySelectorAll('a[href^="#"]').forEach(function (link) {
            link.addEventListener('click', function (e) {
                const href = this.getAttribute('href');
                if (href === '#') return;

                const target = document.querySelector(href);
                if (!target) return;

                e.preventDefault();

                // Close offcanvas if open
                if (offcanvasInstance && offcanvasEl.classList.contains('show')) {
                    offcanvasInstance.hide();
                }

                const top = target.getBoundingClientRect().top + window.pageYOffset - NAVBAR_HEIGHT;
                window.scrollTo({ top: top, behavior: 'smooth' });
            });
        });

        // ─── Scroll Reveal (Intersection Observer) ──────────────
        const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

        if (!prefersReducedMotion) {
            const revealObserver = new IntersectionObserver(function (entries) {
                entries.forEach(function (entry) {
                    if (entry.isIntersecting) {
                        entry.target.classList.add('visible');
                        revealObserver.unobserve(entry.target);
                    }
                });
            }, { threshold: 0.15 });

            document.querySelectorAll('.fade-in-up').forEach(function (el) {
                revealObserver.observe(el);
            });
        } else {
            // Show everything immediately
            document.querySelectorAll('.fade-in-up').forEach(function (el) {
                el.classList.add('visible');
            });
        }

        // ─── Counter Animation ──────────────────────────────────
        function easeOutQuad(t) {
            return t * (2 - t);
        }

        function animateCounter(el) {
            const target = parseInt(el.getAttribute('data-target'), 10);
            const suffix = el.getAttribute('data-suffix') || '';
            const duration = 2000;
            let startTime = null;

            function step(timestamp) {
                if (!startTime) startTime = timestamp;
                const elapsed = timestamp - startTime;
                const progress = Math.min(elapsed / duration, 1);
                const easedProgress = easeOutQuad(progress);
                const current = Math.floor(easedProgress * target);
                el.textContent = current + suffix;
                if (progress < 1) {
                    requestAnimationFrame(step);
                } else {
                    el.textContent = target + suffix;
                }
            }

            requestAnimationFrame(step);
        }

        const counterObserver = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    if (prefersReducedMotion) {
                        // Show final value immediately without animation
                        var target = parseInt(entry.target.getAttribute('data-target'), 10);
                        var suffix = entry.target.getAttribute('data-suffix') || '';
                        entry.target.textContent = target + suffix;
                    } else {
                        animateCounter(entry.target);
                    }
                    counterObserver.unobserve(entry.target);
                }
            });
        }, { threshold: 0.3 });

        document.querySelectorAll('.counter').forEach(function (el) {
            counterObserver.observe(el);
        });

        // ─── Form Validation & Submission ───────────────────────
        const form = document.getElementById('enquiryForm');
        const formContent = document.getElementById('formContent');
        const formSuccess = document.getElementById('formSuccess');
        const submitBtn = document.getElementById('submitBtn');
        const submitAnother = document.getElementById('submitAnother');
        const srAnnouncements = document.getElementById('srAnnouncements');

        // Field references
        const fields = {
            fullName: document.getElementById('fullName'),
            email: document.getElementById('email'),
            phone: document.getElementById('phone'),
            course: document.getElementById('course'),
            message: document.getElementById('message')
        };

        // Validation rules
        const validators = {
            fullName: function (value) {
                value = value.trim();
                if (!value) return 'Please enter your full name.';
                if (value.length < 2) return 'Name must be at least 2 characters.';
                if (value.length > 100) return 'Name must not exceed 100 characters.';
                if (!/^[\p{L}\p{M}\s.'-]+$/u.test(value)) return 'Name should contain only letters and spaces.';
                return '';
            },
            email: function (value) {
                value = value.trim();
                if (!value) return 'Please enter your email address.';
                if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(value)) return 'Please enter a valid email address.';
                return '';
            },
            phone: function (value) {
                value = value.trim();
                if (!value) return 'Please enter your mobile number.';
                if (!/^[6-9]\d{9}$/.test(value)) return 'Please enter a valid 10-digit Indian mobile number starting with 6–9.';
                return '';
            },
            course: function (value) {
                if (!value) return 'Please select a programme of interest.';
                return '';
            },
            message: function (value) {
                if (value && value.length > 500) return 'Message must not exceed 500 characters.';
                return '';
            }
        };

        function validateField(name) {
            var field = fields[name];
            var error = validators[name](field.value);
            var feedbackEl = document.getElementById(name + 'Feedback');

            if (error) {
                field.classList.remove('is-valid');
                field.classList.add('is-invalid');
                if (feedbackEl) feedbackEl.textContent = error;
                return false;
            } else {
                field.classList.remove('is-invalid');
                // Only mark valid if field has a value (skip optional empty fields)
                if (field.value.trim() || field.required) {
                    field.classList.add('is-valid');
                }
                if (feedbackEl) feedbackEl.textContent = '';
                return true;
            }
        }

        // Validate on blur
        ['fullName', 'email', 'phone', 'course'].forEach(function (name) {
            fields[name].addEventListener('blur', function () {
                validateField(name);
            });

            // Clear invalid state on input (real-time feedback)
            fields[name].addEventListener('input', function () {
                if (this.classList.contains('is-invalid')) {
                    validateField(name);
                }
            });
        });

        // Select elements also need change event
        fields.course.addEventListener('change', function () {
            validateField('course');
        });

        // Phone: strip country code prefix, allow only digits
        fields.phone.addEventListener('input', function () {
            var v = this.value.replace(/\D/g, '');
            // Strip leading 91 if user pasted +91XXXXXXXXXX (12+ digits)
            if (v.length > 10 && v.startsWith('91')) {
                v = v.substring(2);
            }
            this.value = v.slice(0, 10);
        });

        // ─── Character Counter ──────────────────────────────────
        var charCount = document.getElementById('charCount');
        var messageCounter = document.getElementById('messageCounter');

        fields.message.addEventListener('input', function () {
            var len = this.value.length;
            charCount.textContent = len;
            if (len > 450) {
                messageCounter.classList.add('char-warning');
            } else {
                messageCounter.classList.remove('char-warning');
            }
        });

        // ─── Form Submit ────────────────────────────────────────
        form.addEventListener('submit', function (e) {
            e.preventDefault();

            var allValid = true;
            var firstInvalid = null;

            ['fullName', 'email', 'phone', 'course', 'message'].forEach(function (name) {
                var valid = validateField(name);
                if (!valid && allValid) {
                    allValid = false;
                    firstInvalid = fields[name];
                }
            });

            if (!allValid) {
                // Shake the button
                submitBtn.classList.add('shake');
                setTimeout(function () {
                    submitBtn.classList.remove('shake');
                }, 500);

                // Scroll to and focus first invalid field
                if (firstInvalid) {
                    var top = firstInvalid.getBoundingClientRect().top + window.pageYOffset - NAVBAR_HEIGHT - 20;
                    window.scrollTo({ top: top, behavior: 'smooth' });
                    setTimeout(function () {
                        firstInvalid.focus();
                    }, 400);
                }

                announce('Please correct the errors in the form before submitting.');
                return;
            }

            // Show loading state
            submitBtn.disabled = true;
            submitBtn.classList.add('btn-loading');

            // Simulate async submission (frontend-only — no actual backend)
            setTimeout(function () {
                submitBtn.disabled = false;
                submitBtn.classList.remove('btn-loading');

                // Show success
                formContent.classList.add('d-none');
                formSuccess.classList.remove('d-none');
                formSuccess.focus();

                announce('Your demonstration enquiry passed validation checks.');
            }, 1500);
        });

        // ─── Submit Another ─────────────────────────────────────
        submitAnother.addEventListener('click', function () {
            form.reset();

            // Clear all validation classes
            Object.keys(fields).forEach(function (name) {
                fields[name].classList.remove('is-valid', 'is-invalid');
            });
            charCount.textContent = '0';
            messageCounter.classList.remove('char-warning');

            // Swap visibility
            formSuccess.classList.add('d-none');
            formContent.classList.remove('d-none');

            // Focus first field
            fields.fullName.focus();

            announce('Form has been reset. You can submit a new enquiry.');
        });

        // ─── Screen Reader Announcements ────────────────────────
        function announce(message) {
            if (srAnnouncements) {
                srAnnouncements.textContent = '';
                // Small delay so screen readers detect the change
                setTimeout(function () {
                    srAnnouncements.textContent = message;
                }, 100);
            }
        }

        // ─── Back to Top Button ─────────────────────────────────
        var backToTop = document.getElementById('backToTop');
        var topTicking = false;

        function handleTopBtn() {
            if (window.scrollY > 300) {
                backToTop.classList.add('visible');
            } else {
                backToTop.classList.remove('visible');
            }
            topTicking = false;
        }

        window.addEventListener('scroll', function () {
            if (!topTicking) {
                requestAnimationFrame(handleTopBtn);
                topTicking = true;
            }
        }, { passive: true });

        backToTop.addEventListener('click', function () {
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });

        // ─── Current Year in Footer ─────────────────────────────
        var yearEl = document.querySelector('.current-year');
        if (yearEl) {
            yearEl.textContent = new Date().getFullYear();
        }

    }); // end DOMContentLoaded
})();
