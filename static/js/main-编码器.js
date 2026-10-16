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

    // Custom controls for homepage product videos
    document.querySelectorAll('[data-video-player]').forEach(player => {
        const video = player.querySelector('video');
        const playButtons = player.querySelectorAll('[data-video-play]');
        const seek = player.querySelector('[data-video-seek]');
        const playedTrack = player.querySelector('[data-video-played]');
        const timeDisplay = player.querySelector('[data-video-time]');
        const muteButton = player.querySelector('[data-video-mute]');
        const volume = player.querySelector('[data-video-volume]');
        const fullscreenButton = player.querySelector('[data-video-fullscreen]');
        const status = player.querySelector('[data-video-status]');

        if (!video || !seek || !playedTrack || !timeDisplay) return;
        let draggingSeek = false;
        let seekPointerId = null;
        let dragTime = 0;
        let playbackFrame = 0;

        const formatTime = seconds => {
            if (!Number.isFinite(seconds) || seconds < 0) return '0:00';
            const wholeSeconds = Math.floor(seconds);
            const minutes = Math.floor(wholeSeconds / 60);
            const remainder = String(wholeSeconds % 60).padStart(2, '0');
            if (minutes < 60) return `${minutes}:${remainder}`;
            const hours = Math.floor(minutes / 60);
            return `${hours}:${String(minutes % 60).padStart(2, '0')}:${remainder}`;
        };

        const updateVolume = () => {
            if (!volume) return;
            const level = video.muted ? 0 : video.volume;
            volume.value = String(level);
            volume.style.setProperty('--video-volume', `${level * 100}%`);
        };

        const updateSeek = () => {
            const duration = video.duration;
            const hasDuration = Number.isFinite(duration) && duration > 0;
            const currentTime = draggingSeek ? dragTime : video.currentTime;
            const progress = hasDuration ? Math.min(Math.max(currentTime / duration, 0), 1) : 0;
            seek.setAttribute('aria-disabled', String(!hasDuration));
            seek.setAttribute('aria-valuemin', '0');
            seek.setAttribute('aria-valuemax', hasDuration ? String(duration) : '0');
            seek.setAttribute('aria-valuenow', hasDuration ? String(currentTime) : '0');
            seek.style.setProperty('--video-progress', `${progress * 100}%`);
            playedTrack.style.width = `${progress * 100}%`;
            seek.setAttribute('aria-valuetext', `${formatTime(currentTime)} of ${formatTime(duration)}`);
            timeDisplay.textContent = `${formatTime(currentTime)} / ${formatTime(duration)}`;
        };

        const seekToPointer = event => {
            const duration = video.duration;
            if (!Number.isFinite(duration) || duration <= 0) return;
            const bounds = seek.getBoundingClientRect();
            if (bounds.width <= 0) return;
            const position = Math.min(Math.max((event.clientX - bounds.left) / bounds.width, 0), 1);
            dragTime = position * duration;
            video.currentTime = dragTime;
            updateSeek();
        };

        seek.addEventListener('pointerdown', event => {
            if (event.button !== 0 || seek.getAttribute('aria-disabled') === 'true') return;
            event.preventDefault();
            draggingSeek = true;
            seekPointerId = event.pointerId;
            seek.setPointerCapture(event.pointerId);
            seek.classList.add('is-seeking');
            seekToPointer(event);
        });
        seek.addEventListener('pointermove', event => {
            if (draggingSeek && event.pointerId === seekPointerId) seekToPointer(event);
        });
        const endSeeking = event => {
            if (!draggingSeek || event.pointerId !== seekPointerId) return;
            draggingSeek = false;
            seekPointerId = null;
            seek.classList.remove('is-seeking');
            updateSeek();
        };
        seek.addEventListener('pointerup', endSeeking);
        seek.addEventListener('pointercancel', endSeeking);
        seek.addEventListener('lostpointercapture', endSeeking);
        seek.addEventListener('keydown', event => {
            const duration = video.duration;
            if (!Number.isFinite(duration) || duration <= 0) return;
            let targetTime;
            const step = event.shiftKey ? 10 : 5;
            if (event.key === 'ArrowLeft' || event.key === 'ArrowDown') targetTime = video.currentTime - step;
            else if (event.key === 'ArrowRight' || event.key === 'ArrowUp') targetTime = video.currentTime + step;
            else if (event.key === 'Home') targetTime = 0;
            else if (event.key === 'End') targetTime = duration;
            else return;
            event.preventDefault();
            video.currentTime = Math.min(Math.max(targetTime, 0), duration);
            updateSeek();
        });

        const updatePlayState = () => {
            const isPlaying = !video.paused && !video.ended;
            player.classList.toggle('is-playing', isPlaying);
            playButtons.forEach(button => {
                const title = video.getAttribute('aria-label') || 'video';
                button.setAttribute('aria-label', `${isPlaying ? 'Pause' : 'Play'} ${title}`);
                button.setAttribute('aria-pressed', String(isPlaying));
                const icon = button.querySelector('i');
                if (icon) {
                    icon.classList.toggle('ri-play-fill', !isPlaying);
                    icon.classList.toggle('ri-pause-fill', isPlaying);
                }
            });
        };

        const play = () => {
            if (status) status.textContent = '';
            const playback = video.play();
            if (playback && typeof playback.catch === 'function') {
                playback.catch(() => {
                    if (status) status.textContent = 'Playback could not be started. Please try again.';
                    updatePlayState();
                });
            }
        };

        playButtons.forEach(button => button.addEventListener('click', () => {
            if (video.paused || video.ended) play();
            else video.pause();
        }));
        video.addEventListener('click', () => {
            if (video.paused || video.ended) play();
            else video.pause();
        });
        video.addEventListener('keydown', event => {
            if (event.code === 'Space' || event.code === 'KeyK') {
                event.preventDefault();
                if (video.paused || video.ended) play();
                else video.pause();
            }
        });

        if (muteButton) {
            muteButton.addEventListener('click', () => {
                video.muted = !video.muted;
            });
            video.addEventListener('volumechange', () => {
                const isMuted = video.muted || video.volume === 0;
                muteButton.setAttribute('aria-label', `${isMuted ? 'Unmute' : 'Mute'} ${video.getAttribute('aria-label') || 'video'}`);
                muteButton.setAttribute('aria-pressed', String(isMuted));
                const icon = muteButton.querySelector('i');
                if (icon) {
                    icon.classList.toggle('ri-volume-mute-line', isMuted);
                    icon.classList.toggle('ri-volume-up-line', !isMuted);
                }
                updateVolume();
            });
        }

        if (volume) {
            volume.addEventListener('input', () => {
                video.volume = Number(volume.value);
                video.muted = video.volume === 0;
                updateVolume();
            });
            updateVolume();
        }

        if (fullscreenButton) {
            fullscreenButton.addEventListener('click', async () => {
                try {
                    if (document.fullscreenElement) await document.exitFullscreen();
                    else if (player.requestFullscreen) await player.requestFullscreen();
                    else if (video.webkitEnterFullscreen) video.webkitEnterFullscreen();
                    else if (status) status.textContent = 'Fullscreen is not supported by this browser.';
                } catch {
                    if (status) status.textContent = 'Fullscreen could not be opened.';
                }
            });
            document.addEventListener('fullscreenchange', () => {
                const isFullscreen = document.fullscreenElement === player;
                fullscreenButton.setAttribute('aria-label', `${isFullscreen ? 'Exit' : 'Enter'} fullscreen for ${video.getAttribute('aria-label') || 'video'}`);
                const icon = fullscreenButton.querySelector('i');
                if (icon) {
                    icon.classList.toggle('ri-fullscreen-exit-line', isFullscreen);
                    icon.classList.toggle('ri-fullscreen-line', !isFullscreen);
                }
            });
        }

        ['loadedmetadata', 'durationchange', 'timeupdate', 'seeking', 'seeked'].forEach(eventName => {
            video.addEventListener(eventName, updateSeek);
        });
        const updateWhilePlaying = () => {
            updateSeek();
            if (!video.paused && !video.ended) playbackFrame = requestAnimationFrame(updateWhilePlaying);
            else playbackFrame = 0;
        };
        video.addEventListener('play', () => {
            updatePlayState();
            if (!playbackFrame) playbackFrame = requestAnimationFrame(updateWhilePlaying);
        });
        video.addEventListener('pause', () => {
            updatePlayState();
            if (playbackFrame) cancelAnimationFrame(playbackFrame);
            playbackFrame = 0;
            updateSeek();
        });
        video.addEventListener('ended', () => {
            updatePlayState();
            if (playbackFrame) cancelAnimationFrame(playbackFrame);
            playbackFrame = 0;
            updateSeek();
        });
        video.addEventListener('error', () => {
            if (status) status.textContent = 'This video could not be loaded.';
        });
        updateSeek();
        updatePlayState();
    });

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

    // Expand or collapse homepage service offers
    const servicesToggle = document.getElementById('servicesToggle');
    if (servicesToggle) {
        const extraServices = document.querySelectorAll('#services .service-card:nth-child(n + 7)');
        servicesToggle.addEventListener('click', () => {
            const expanded = servicesToggle.getAttribute('aria-expanded') === 'true';
            extraServices.forEach(card => { card.hidden = expanded; });
            servicesToggle.setAttribute('aria-expanded', String(!expanded));
            servicesToggle.textContent = expanded ? 'Show More' : 'Show Less';
        });
    }

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
        const submissionToken = document.getElementById('contactSubmissionToken');
        const createSubmissionToken = () => {
            if (window.crypto && typeof window.crypto.randomUUID === 'function') {
                return window.crypto.randomUUID();
            }
            return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (character) => {
                const random = Math.random() * 16 | 0;
                return (character === 'x' ? random : (random & 0x3 | 0x8)).toString(16);
            });
        };
        submissionToken.value = createSubmissionToken();
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
                message: document.getElementById('message').value,
                contact_reference_code: document.getElementById('contactReferenceCode').value,
                submission_token: submissionToken.value
            };

            try {
                const res = await fetch('/api/contact', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                const succeeded = res.ok && data.success;
                if (feedback) {
                    feedback.textContent = data.message || 'Something went wrong. Please try again.';
                    feedback.classList.add('show', succeeded ? 'success' : 'error');
                }
                if (succeeded) {
                    btn.textContent = 'Message Sent ✓';
                    contactForm.reset();
                    submissionToken.value = createSubmissionToken();
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
