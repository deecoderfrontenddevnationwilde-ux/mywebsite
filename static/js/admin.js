// Small admin dashboard helpers.

function confirmDelete(label) {
    return confirm('Delete ' + label + '? This cannot be undone.');
}

// Live image preview for the news/product image upload inputs.
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('input[type="file"][accept]').forEach(input => {
        input.addEventListener('change', () => {
            const file = input.files && input.files[0];
            if (!file) return;
            let preview = input.parentElement.querySelector('img.admin-current-image');
            if (!preview) {
                preview = document.createElement('img');
                preview.className = 'admin-current-image';
                input.parentElement.insertBefore(preview, input);
            }
            const reader = new FileReader();
            reader.onload = (e) => { preview.src = e.target.result; };
            reader.readAsDataURL(file);
        });
    });

    // Auto-dismiss admin alerts
    document.querySelectorAll('.admin-alert').forEach(el => {
        setTimeout(() => { el.style.display = 'none'; }, 6000);
    });
});
