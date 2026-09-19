// ============================================================
// Site-wide interactions.
// Ported from the original inline <script> (mobile menu, scroll
// progress, back-to-top, reveal-on-scroll, counters, FAQ) plus
// new AJAX wiring for the newsletter and contact forms so they
// talk to the Flask backend instead of doing nothing / mailto.
// Every selector is guarded so this file works on every page,
// not just the homepage where all sections exist.
// ============================================================

document.addEventListener('DOMContentLoaded', () => {
    // Mobile menu
    const menuBtn = document.getElementById('menuBtn');
    const navLinks = document.getElementById('navLinks');
    if (menuBtn && navLinks) {
        menuBtn.addEventListener('click', () => {
            menuBtn.classList.toggle('active');
            navLinks.classList.toggle('open');
        });
        navLinks.querySelectorAll('a').forEach(a => {
            a.addEventListener('click', () => {
                menuBtn.classList.remove('active');
                navLinks.classList.remove('open');
            });
        });
    }

    // Scroll progress
    const progress = document.getElementById('scrollProgress');
    if (progress) {
        window.addEventListener('scroll', () => {
            const h = document.documentElement.scrollHeight - window.innerHeight;
            progress.style.width = (h > 0 ? window.scrollY / h * 100 : 0) + '%';
        });
    }

    // Back to top
    const backTop = document.getElementById('backTop');
    if (backTop) {
        window.addEventListener('scroll', () => {
            backTop.classList.toggle('show', window.scrollY > 400);
        });
        backTop.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));
    }

    // Reveal on scroll
    const revealObs = new IntersectionObserver((entries) => {
        entries.forEach(e => {
            if (e.isIntersecting) {
                e.target.classList.add('visible');
                if (e.target.classList.contains('skill-cat')) e.target.classList.add('revealed');
                revealObs.unobserve(e.target);
            }
        });
    }, { threshold: 0.12, rootMargin: '0px 0px -30px 0px' });
    document.querySelectorAll('.reveal, .skill-cat').forEach(el => revealObs.observe(el));

    // Counters
    let counted = false;
    const counterObs = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting && !counted) {
                counted = true;
                document.querySelectorAll('.counter').forEach(c => {
                    const target = +c.dataset.target;
                    const start = performance.now();
                    const dur = 1600;
                    const tick = (now) => {
                        const p = Math.min((now - start) / dur, 1);
                        const eased = 1 - Math.pow(1 - p, 3);
                        const val = Math.floor(eased * target);
                        c.textContent = target === 99 ? val + '%' : val + '+';
                        if (p < 1) requestAnimationFrame(tick);
                    };
                    requestAnimationFrame(tick);
                });
            }
        });
    }, { threshold: 0.4 });
    const stats = document.querySelector('.stats-grid');
    if (stats) counterObs.observe(stats);

    // FAQ
    document.querySelectorAll('.faq-question').forEach(btn => {
        btn.addEventListener('click', () => {
            const item = btn.parentElement;
            const open = item.classList.contains('active');
            document.querySelectorAll('.faq-item').forEach(i => {
                i.classList.remove('active');
                i.querySelector('.faq-answer').style.maxHeight = null;
                i.querySelector('.faq-question').setAttribute('aria-expanded', 'false');
            });
            if (!open) {
                item.classList.add('active');
                const ans = item.querySelector('.faq-answer');
                ans.style.maxHeight = ans.scrollHeight + 'px';
                btn.setAttribute('aria-expanded', 'true');
            }
        });
    });

    // Active nav link highlighting while scrolling the homepage
    const sections = document.querySelectorAll('header[id], section[id]');
    const links = document.querySelectorAll('.nav-links a:not(.nav-cta)');
    if (sections.length && links.length) {
        window.addEventListener('scroll', () => {
            let cur = '';
            sections.forEach(s => {
                if (window.scrollY >= s.offsetTop - 140) cur = s.id;
            });
            links.forEach(a => {
                const href = a.getAttribute('href') || '';
                a.classList.toggle('active', href.endsWith('#' + cur) && cur !== '');
            });
        });
    }

    // Auto-dismiss server-rendered flash messages
    const flashMessages = document.getElementById('flashMessages');
    if (flashMessages) {
        setTimeout(() => { flashMessages.style.display = 'none'; }, 6000);
    }

    // ---------------- Newsletter ("Stay in Touch") — AJAX ----------------
    const newsletterForm = document.getElementById('newsletterForm');
    if (newsletterForm) {
        const feedback = document.getElementById('newsletterFeedback');
        newsletterForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const emailInput = document.getElementById('newsletterEmail');
            const btn = newsletterForm.querySelector('button[type="submit"]');
            const email = emailInput.value.trim();
            const origText = btn.textContent;

            btn.disabled = true;
            btn.textContent = '...';
            feedback.className = 'form-feedback';

            try {
                const res = await fetch('/api/subscribe', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email })
                });
                const data = await res.json();
                feedback.textContent = data.message;
                feedback.classList.add('show', data.success ? 'success' : 'error');
                if (data.success) newsletterForm.reset();
            } catch (err) {
                feedback.textContent = 'Something went wrong. Please try again.';
                feedback.classList.add('show', 'error');
            } finally {
                btn.disabled = false;
                btn.textContent = origText;
            }
        });
    }

    // ---------------- Contact form — AJAX ----------------
    const contactForm = document.getElementById('contactForm');
    if (contactForm) {
        const feedback = document.getElementById('contactFeedback');
        contactForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = contactForm.querySelector('button[type="submit"]');
            const orig = btn.textContent;
            btn.textContent = 'Sending...';
            btn.disabled = true;
            if (feedback) feedback.className = 'form-feedback';

            const payload = {
                name: document.getElementById('name').value,
                email: document.getElementById('email').value,
                subject: document.getElementById('service') ? document.getElementById('service').value : '',
                message: document.getElementById('message').value
            };

            try {
                const res = await fetch('/api/contact', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                if (feedback) {
                    feedback.textContent = data.message;
                    feedback.classList.add('show', data.success ? 'success' : 'error');
                }
                if (data.success) {
                    btn.textContent = 'Message Sent ✓';
                    contactForm.reset();
                } else {
                    btn.textContent = orig;
                }
            } catch (err) {
                if (feedback) {
                    feedback.textContent = 'Something went wrong. Please try again.';
                    feedback.classList.add('show', 'error');
                }
                btn.textContent = orig;
            } finally {
                btn.disabled = false;
                setTimeout(() => { btn.textContent = orig; }, 2500);
            }
        });
    }
});
