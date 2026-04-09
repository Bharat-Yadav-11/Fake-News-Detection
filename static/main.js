document.addEventListener('DOMContentLoaded', () => {
    const nav = document.querySelector('.nav');
    const mobileMenuBtn = document.getElementById('mobileMenuBtn');
    const navLinks = document.getElementById('navLinks');
    const navItems = document.querySelectorAll('[data-nav-link]');

    // ===== SCROLL ANIMATIONS =====
    const observerOptions = {
        root: null,
        rootMargin: '0px',
        threshold: 0.1
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
            }
        });
    }, observerOptions);

    document.querySelectorAll('.animate-on-scroll').forEach(el => {
        observer.observe(el);
    });

    // ===== MOBILE MENU =====
    if (mobileMenuBtn && navLinks) {
        mobileMenuBtn.addEventListener('click', () => {
            navLinks.classList.toggle('active');
        });
    }

    // ===== DEMO PROGRESS BARS ANIMATION =====
    const animateProgressBars = () => {
        const progressBars = document.querySelectorAll('.demo-progress-bar');
        progressBars.forEach(bar => {
            const targetWidth = bar.style.getPropertyValue('--target-width');
            setTimeout(() => {
                bar.style.width = targetWidth;
            }, 500);
        });
    };

    // Trigger when hero section is visible
    const heroObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                animateProgressBars();
                heroObserver.unobserve(entry.target);
            }
        });
    }, { threshold: 0.3 });

    const heroDemo = document.querySelector('.hero-demo');
    if (heroDemo) {
        heroObserver.observe(heroDemo);
    }

    // ===== LIVE TERMINAL ANIMATION =====
    const terminalBody = document.getElementById('terminalBody');
    const runAnalysisBtn = document.getElementById('runAnalysis');

    if (terminalBody && runAnalysisBtn) {
        const terminalSequence = [
            { type: 'command', text: 'fakeshield analyze --claim "Gold price in Delhi reaches ₹72,500 per 10 grams"' },
            { type: 'output', text: 'Initializing FakeShield Analysis Engine v2.1...' },
            { type: 'output', text: '' },
            { type: 'success', text: '✓ Local ML model loaded (passive-aggressive-classifier)' },
            { type: 'output', text: '  → Running pattern analysis on claim text...' },
            { type: 'progress', value: 100, label: 'Pattern Analysis' },
            { type: 'output', text: '' },
            { type: 'success', text: '✓ Local Model Score: 78% confidence (Likely Verifiable)' },
            { type: 'output', text: '' },
            { type: 'output', text: 'Starting live source verification...' },
            { type: 'output', text: '  → Querying trusted financial sources...' },
            { type: 'progress', value: 100, label: 'Source Lookup' },
            { type: 'output', text: '' },
            { type: 'success', text: '✓ Found 4 matching sources:' },
            { type: 'output', text: '    1. economictimes.com - SUPPORTS (published 2h ago)' },
            { type: 'output', text: '    2. moneycontrol.com - SUPPORTS (published 4h ago)' },
            { type: 'warning', text: '    3. twitter.com/user123 - NEEDS REVIEW (unverified)' },
            { type: 'output', text: '    4. reuters.com - SUPPORTS (published 1h ago)' },
            { type: 'output', text: '' },
            { type: 'output', text: '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━' },
            { type: 'success', text: '✓ ANALYSIS COMPLETE' },
            { type: 'output', text: '' },
            { type: 'output', text: '  Verdict: HIGH CONFIDENCE - Claim appears verifiable' },
            { type: 'output', text: '  Local Score: 78% | Live Sources: 3/4 supporting' },
            { type: 'output', text: '  Recommendation: Review linked sources for final confirmation' },
            { type: 'output', text: '' },
            { type: 'cursor', text: '' }
        ];

        let isAnimating = false;

        async function runTerminalAnimation() {
            if (isAnimating) return;
            isAnimating = true;

            terminalBody.innerHTML = '';
            runAnalysisBtn.disabled = true;
            runAnalysisBtn.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spinner"><circle cx="12" cy="12" r="10" stroke-dasharray="31.416" stroke-dashoffset="10"/></svg> Loading...';

            for (let i = 0; i < terminalSequence.length; i++) {
                const item = terminalSequence[i];
                await new Promise(resolve => setTimeout(resolve, item.type === 'progress' ? 100 : 150));

                const line = document.createElement('div');
                line.className = 'terminal-line';

                if (item.type === 'command') {
                    line.innerHTML = `<span class="terminal-prompt">$ </span><span class="terminal-command">${item.text}</span>`;
                } else if (item.type === 'progress') {
                    line.innerHTML = `
                        <div class="terminal-progress">
                            <span class="terminal-output">${item.label}</span>
                            <div class="terminal-progress-bar">
                                <div class="terminal-progress-fill" id="progress-${i}"></div>
                            </div>
                            <span class="terminal-output" id="progress-text-${i}">0%</span>
                        </div>
                    `;
                } else if (item.type === 'success') {
                    line.innerHTML = `<span class="terminal-success">${item.text}</span>`;
                } else if (item.type === 'warning') {
                    line.innerHTML = `<span class="terminal-warning">${item.text}</span>`;
                } else if (item.type === 'cursor') {
                    line.innerHTML = `<span class="terminal-prompt">$ </span><span class="terminal-cursor"></span>`;
                } else {
                    line.innerHTML = `<span class="terminal-output">${item.text}</span>`;
                }

                terminalBody.appendChild(line);

                // Trigger animation
                await new Promise(resolve => setTimeout(resolve, 50));
                line.classList.add('visible');

                // Animate progress bar
                if (item.type === 'progress') {
                    const progressFill = document.getElementById(`progress-${i}`);
                    const progressText = document.getElementById(`progress-text-${i}`);
                    let progress = 0;
                    const interval = setInterval(() => {
                        progress += 5;
                        if (progress >= item.value) {
                            progress = item.value;
                            clearInterval(interval);
                        }
                        if (progressFill) progressFill.style.width = `${progress}%`;
                        if (progressText) progressText.textContent = `${progress}%`;
                    }, 30);
                    await new Promise(resolve => setTimeout(resolve, 600));
                }

                // Auto-scroll
                terminalBody.scrollTop = terminalBody.scrollHeight;
            }

            runAnalysisBtn.disabled = false;
            runAnalysisBtn.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg> Run Demo Analysis';
            isAnimating = false;
        }

        runAnalysisBtn.addEventListener('click', runTerminalAnimation);

        // Auto-run terminal animation when section is visible
        const terminalObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting && !isAnimating) {
                    runTerminalAnimation();
                    terminalObserver.unobserve(entry.target);
                }
            });
        }, { threshold: 0.5 });

        const terminalSection = document.querySelector('.terminal-section');
        if (terminalSection) {
            terminalObserver.observe(terminalSection);
        }
    }

    // ===== NEWSLETTER FORM =====
    const newsletterForm = document.getElementById('newsletterForm');
    if (newsletterForm) {
        newsletterForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const email = e.target.querySelector('input').value;
            alert(`Thanks for subscribing with ${email}! You'll receive updates about FakeShield.`);
            e.target.reset();
        });
    }

    // ===== SMOOTH SCROLL FOR ANCHOR LINKS =====
    const setActiveNavLink = (activeLink) => {
        navItems.forEach(link => {
            const isActive = link === activeLink;
            link.classList.toggle('active', isActive);
            if (isActive) {
                link.setAttribute('aria-current', 'page');
            } else {
                link.removeAttribute('aria-current');
            }
        });
    };

    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            const href = this.getAttribute('href');
            const target = document.querySelector(href);
            if (!target) return;
            e.preventDefault();

            const navHeight = nav ? nav.offsetHeight : 0;
            const targetTop = target.getBoundingClientRect().top + window.pageYOffset - navHeight - 12;

            if (this.matches('[data-nav-link]')) {
                setActiveNavLink(this);
            }

            window.scrollTo({
                top: targetTop,
                behavior: 'smooth'
            });

            if (navLinks) navLinks.classList.remove('active');
        });
    });

    // ===== NAV SCROLL EFFECT =====
    window.addEventListener('scroll', () => {
        if (!nav) return;
        const currentScroll = window.pageYOffset;
        if (currentScroll > 100) {
            nav.style.boxShadow = '0 4px 20px rgba(0,0,0,0.08)';
        } else {
            nav.style.boxShadow = 'none';
        }
    });

    // ===== ACTIVE NAV LINK ON SCROLL (homepage) =====
    const sections = document.querySelectorAll('section[id]');

    if (sections.length > 0 && navItems.length > 0) {
        const updateActiveNav = () => {
            const scrollY = window.pageYOffset + ((nav ? nav.offsetHeight : 0) + 80);

            let currentSection = 'home';
            sections.forEach(section => {
                const sectionTop = section.offsetTop;
                const sectionHeight = section.offsetHeight;
                if (scrollY >= sectionTop && scrollY < sectionTop + sectionHeight) {
                    currentSection = section.getAttribute('id');
                }
            });

            const matchingLink = document.querySelector(`.nav-links a[data-section="${currentSection}"]`);
            if (matchingLink) {
                setActiveNavLink(matchingLink);
            }
        };

        window.addEventListener('scroll', updateActiveNav);
        window.addEventListener('load', updateActiveNav);
        updateActiveNav();
    }

    // ===== PREDICTION PAGE: WORD COUNT + VALIDATION + LOADER =====
    const predictForm = document.getElementById('predictForm');
    const textarea = document.getElementById('news');
    const charCountEl = document.getElementById('charCount');
    const wordCountEl = document.getElementById('wordCount');
    const analyzeBtn = document.getElementById('analyzeBtn');
    const validationToast = document.getElementById('validationToast');
    const validationMessage = document.getElementById('validationMessage');
    const validationText = 'Please enter a claim of at least 10 words for accurate analysis.';

    if (textarea && charCountEl && wordCountEl) {
        const updateCounts = () => {
            const text = textarea.value.trim();
            const chars = textarea.value.length;
            const words = text ? text.split(/\s+/).length : 0;
            charCountEl.textContent = `${chars} character${chars !== 1 ? 's' : ''}`;
            wordCountEl.textContent = `${words} word${words !== 1 ? 's' : ''}`;
        };

        textarea.addEventListener('input', updateCounts);
        // Initial count on page load
        updateCounts();
    }

    if (predictForm && analyzeBtn && validationToast) {
        predictForm.addEventListener('submit', (e) => {
            const text = textarea.value.trim();
            const words = text ? text.split(/\s+/).length : 0;

            if (!text || words < 10) {
                e.preventDefault();
                showValidation(validationText);
                textarea.focus();
                return;
            }

            // All good — show loader on button
            const btnIcon = analyzeBtn.querySelector('.btn-icon');
            const btnText = analyzeBtn.querySelector('.btn-text');
            const btnLoader = analyzeBtn.querySelector('.btn-loader');
            if (btnLoader) {
                btnLoader.innerHTML = '<svg class="spinner" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10" stroke-dasharray="31.416" stroke-dashoffset="10"/></svg> Loading...';
            }
            if (btnIcon) btnIcon.style.display = 'none';
            if (btnText) btnText.style.display = 'none';
            if (btnLoader) btnLoader.style.display = 'inline-flex';
            analyzeBtn.disabled = true;
            analyzeBtn.classList.add('loading');
        });
    }

    function showValidation(msg) {
        if (!validationToast || !validationMessage) return;
        validationMessage.textContent = msg;
        validationToast.classList.add('show');
        // Auto-hide after 4 seconds
        clearTimeout(window._validationTimeout);
        window._validationTimeout = setTimeout(() => {
            validationToast.classList.remove('show');
        }, 3000);
    }
});
