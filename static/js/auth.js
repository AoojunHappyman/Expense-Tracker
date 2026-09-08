const authForm = document.querySelector('.auth-form');
if (authForm) {
    const button = authForm.querySelector('button[type="submit"]');
    const originalLabel = button.textContent;
    let submitting = false;
    authForm.addEventListener('submit', (event) => {
        if (submitting) {
            event.preventDefault();
            return;
        }
        submitting = true;
        button.disabled = true;
        button.textContent = 'กำลังดำเนินการ…';
        authForm.setAttribute('aria-busy', 'true');
    });
    window.addEventListener('pageshow', () => {
        submitting = false;
        button.disabled = false;
        button.textContent = originalLabel;
        authForm.removeAttribute('aria-busy');
    });
}
