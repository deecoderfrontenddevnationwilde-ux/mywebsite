// Small admin dashboard helpers.

function confirmDelete(label) {
    return confirm('Delete ' + label + '? This cannot be undone.');
}

document.addEventListener('DOMContentLoaded', () => {
    const chunkedVideoForm = document.querySelector('[data-chunked-video-upload]');
    if (chunkedVideoForm) {
        const fileInput = chunkedVideoForm.querySelector('[data-video-file]');
        const dropzone = chunkedVideoForm.querySelector('[data-video-dropzone]');
        const browseButton = chunkedVideoForm.querySelector('[data-video-browse]');
        const previewPanel = chunkedVideoForm.querySelector('[data-video-preview-panel]');
        const preview = chunkedVideoForm.querySelector('[data-video-preview]');
        const duration = chunkedVideoForm.querySelector('[data-video-duration]');
        const fileDetails = chunkedVideoForm.querySelector('[data-video-file-details]');
        const filename = chunkedVideoForm.querySelector('[data-video-filename]');
        const fileMeta = chunkedVideoForm.querySelector('[data-video-file-meta]');
        const fileError = chunkedVideoForm.querySelector('[data-video-file-error]');
        const statusPanel = chunkedVideoForm.querySelector('[data-video-upload-progress]');
        const statusTitle = chunkedVideoForm.querySelector('[data-video-status-title]');
        const status = chunkedVideoForm.querySelector('[data-video-upload-status]');
        const statusIcon = chunkedVideoForm.querySelector('[data-video-status-icon]');
        const progressBar = chunkedVideoForm.querySelector('[data-video-progress]');
        const progressValue = chunkedVideoForm.querySelector('[data-video-progress-value]');
        const submitButton = chunkedVideoForm.querySelector('button[type="submit"]');
        const hasExistingVideo = Boolean(chunkedVideoForm.dataset.videoId);
        let previewUrl = null;

        const setStatus = (state, title, message, icon) => {
            statusPanel.dataset.videoUploadState = state;
            statusTitle.textContent = title;
            status.textContent = message;
            statusIcon.innerHTML = `<i class="${icon}" aria-hidden="true"></i>`;
        };

        const readableSize = bytes => {
            if (bytes >= 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
            if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
            return `${Math.max(1, Math.round(bytes / 1024))} KB`;
        };

        const formatDuration = seconds => {
            if (!Number.isFinite(seconds)) return '';
            const totalSeconds = Math.floor(seconds);
            const hours = Math.floor(totalSeconds / 3600);
            const minutes = Math.floor((totalSeconds % 3600) / 60);
            const remainder = totalSeconds % 60;
            return hours
                ? `${hours}:${String(minutes).padStart(2, '0')}:${String(remainder).padStart(2, '0')}`
                : `${minutes}:${String(remainder).padStart(2, '0')}`;
        };

        const readDuration = () => {
            const value = formatDuration(preview.duration);
            duration.textContent = value ? `Duration · ${value}` : '';
        };
        preview.addEventListener('loadedmetadata', readDuration);
        preview.addEventListener('durationchange', readDuration);

        const inspectFile = file => {
            fileError.hidden = true;
            fileError.textContent = '';
            const extension = file.name.split('.').pop().toLowerCase();
            if (!['mp4', 'webm'].includes(extension)) {
                fileDetails.hidden = true;
                previewPanel.hidden = !hasExistingVideo;
                fileError.textContent = 'This format is not supported. Choose an MP4 or WEBM video.';
                fileError.hidden = false;
                setStatus('failed', 'Unsupported file', fileError.textContent, 'ri-error-warning-line');
                return false;
            }
            const maxBytes = Number(chunkedVideoForm.dataset.maxVideoSize);
            if (file.size > maxBytes) {
                fileDetails.hidden = true;
                previewPanel.hidden = !hasExistingVideo;
                fileError.textContent = `This video is ${(file.size / (1024 * 1024)).toFixed(1)} MB. The configured limit is ${chunkedVideoForm.dataset.maxVideoMb} MB.`;
                fileError.hidden = false;
                setStatus('failed', 'File exceeds upload limit', fileError.textContent, 'ri-error-warning-line');
                return false;
            }
            if (file.size === 0) {
                fileDetails.hidden = true;
                previewPanel.hidden = !hasExistingVideo;
                fileError.textContent = 'This file is empty. Choose a valid video file.';
                fileError.hidden = false;
                setStatus('failed', 'Empty video file', fileError.textContent, 'ri-error-warning-line');
                return false;
            }

            filename.textContent = file.name;
            fileMeta.textContent = `${readableSize(file.size)} · ${extension.toUpperCase()}${file.type ? ` · ${file.type}` : ''}`;
            fileDetails.hidden = false;
            previewPanel.hidden = false;
            duration.textContent = 'Reading video metadata…';
            if (previewUrl) URL.revokeObjectURL(previewUrl);
            previewUrl = URL.createObjectURL(file);
            preview.src = previewUrl;
            preview.load();
            setStatus('ready', 'Ready to upload', 'Your video is selected. Complete the required details and upload when ready.', 'ri-checkbox-circle-line');
            return true;
        };

        browseButton.addEventListener('click', event => {
            event.stopPropagation();
            fileInput.click();
        });
        dropzone.addEventListener('click', event => {
            if (event.target.closest('button')) return;
            fileInput.click();
        });
        fileInput.addEventListener('change', () => {
            const file = fileInput.files && fileInput.files[0];
            if (file) inspectFile(file);
        });
        ['dragenter', 'dragover'].forEach(type => {
            dropzone.addEventListener(type, event => {
                event.preventDefault();
                dropzone.classList.add('is-dragging');
            });
        });
        ['dragleave', 'drop'].forEach(type => {
            dropzone.addEventListener(type, event => {
                event.preventDefault();
                dropzone.classList.remove('is-dragging');
            });
        });
        dropzone.addEventListener('drop', event => {
            const file = event.dataTransfer.files && event.dataTransfer.files[0];
            if (!file) return;
            const transfer = new DataTransfer();
            transfer.items.add(file);
            fileInput.files = transfer.files;
            inspectFile(file);
        });

        chunkedVideoForm.addEventListener('submit', async event => {
            const file = fileInput.files && fileInput.files[0];
            if (!file) return;
            event.preventDefault();
            if (!inspectFile(file)) return;
            if (!chunkedVideoForm.reportValidity()) return;

            const csrfToken = chunkedVideoForm.querySelector('input[name="csrf_token"]').value;
            const chunkSize = Number(chunkedVideoForm.dataset.chunkSize);
            const chunkCount = Math.ceil(file.size / chunkSize);
            const uploadId = crypto.randomUUID();
            const originalButtonText = submitButton.innerHTML;
            let uploadSucceeded = false;

            const send = async (url, body) => {
                for (let attempt = 0; attempt < 3; attempt += 1) {
                    try {
                        const response = await fetch(url, {
                            method: 'POST',
                            body,
                            credentials: 'same-origin'
                        });
                        let result;
                        try {
                            result = await response.json();
                        } catch {
                            throw new Error(`Upload request failed (${response.status}). The hosting server may have rejected the request.`);
                        }
                        if (!response.ok || !result.success) {
                            const error = new Error(result.message || `Upload request failed (${response.status}).`);
                            error.retryable = response.status === 429 || response.status >= 500;
                            throw error;
                        }
                        return result;
                    } catch (error) {
                        if (attempt === 2 || error.retryable === false) throw error;
                        setStatus('uploading', 'Connection interrupted', `Retrying upload (${attempt + 1}/2)…`, 'ri-refresh-line');
                        await new Promise(resolve => setTimeout(resolve, 500 * (attempt + 1)));
                    }
                }
            };

            submitButton.disabled = true;
            submitButton.innerHTML = '<i class="ri-loader-4-line" aria-hidden="true"></i> Uploading…';
            progressBar.hidden = false;
            progressValue.hidden = false;
            progressBar.value = 0;
            progressValue.textContent = '0%';
            setStatus('uploading', 'Uploading video', `Preparing ${file.name} (${readableSize(file.size)})…`, 'ri-upload-cloud-2-line');

            try {
                for (let index = 0; index < chunkCount; index += 1) {
                    const chunkData = new FormData();
                    chunkData.append('csrf_token', csrfToken);
                    chunkData.append('upload_id', uploadId);
                    chunkData.append('chunk_index', String(index));
                    chunkData.append('chunk', file.slice(index * chunkSize, Math.min((index + 1) * chunkSize, file.size)), 'video.chunk');
                    await send(chunkedVideoForm.dataset.chunkUrl, chunkData);
                    const percentage = Math.round((index + 1) / chunkCount * 90);
                    progressBar.value = percentage;
                    progressValue.textContent = `${percentage}%`;
                    setStatus('uploading', 'Uploading video', `Uploading original video file · ${Math.round((index + 1) / chunkCount * 100)}%`, 'ri-upload-cloud-2-line');
                }

                progressBar.value = 94;
                progressValue.textContent = '94%';
                setStatus('processing', 'Verifying and saving', 'Checking the uploaded file and saving the video details…', 'ri-loader-4-line');
                const completeData = new FormData(chunkedVideoForm);
                completeData.delete('video');
                completeData.append('upload_id', uploadId);
                completeData.append('filename', file.name);
                completeData.append('chunk_count', String(chunkCount));
                if (chunkedVideoForm.dataset.videoId) {
                    completeData.append('video_id', chunkedVideoForm.dataset.videoId);
                }
                const result = await send(chunkedVideoForm.dataset.completeUrl, completeData);
                uploadSucceeded = true;
                progressBar.value = 100;
                progressValue.textContent = '100%';
                setStatus('complete', 'Upload complete', result.message || 'Your video was saved successfully.', 'ri-checkbox-circle-line');
                window.location.assign(result.redirect_url);
            } catch (error) {
                setStatus('failed', 'Upload failed', error.message || 'The video upload failed. Please try again.', 'ri-error-warning-line');
                submitButton.disabled = false;
                submitButton.innerHTML = originalButtonText;
                progressBar.value = 0;
                progressValue.textContent = '0%';
                const abortData = new FormData();
                abortData.append('csrf_token', csrfToken);
                abortData.append('upload_id', uploadId);
                fetch(chunkedVideoForm.dataset.abortUrl, {
                    method: 'POST',
                    body: abortData,
                    credentials: 'same-origin'
                }).catch(() => {});
            } finally {
                if (uploadSucceeded) submitButton.disabled = true;
            }
        });

        const posterInput = chunkedVideoForm.querySelector('[data-video-thumbnail]');
        const posterPreview = chunkedVideoForm.querySelector('[data-video-poster-preview]');
        const posterPlaceholder = chunkedVideoForm.querySelector('[data-video-poster-placeholder]');
        let posterUrl = null;
        posterInput.addEventListener('change', () => {
            posterInput.setCustomValidity('');
            const file = posterInput.files && posterInput.files[0];
            if (!file) return;
            const extension = file.name.split('.').pop().toLowerCase();
            if (!['png', 'jpg', 'jpeg', 'gif', 'webp'].includes(extension)) {
                posterInput.setCustomValidity('Choose a PNG, JPG, GIF, or WEBP poster image.');
                posterInput.reportValidity();
                return;
            }
            if (file.size > Number(posterInput.dataset.maxThumbnailSize)) {
                posterInput.setCustomValidity(`Poster image must be ${posterInput.dataset.maxThumbnailMb} MB or smaller.`);
                posterInput.reportValidity();
                return;
            }
            posterInput.setCustomValidity('');
            if (posterUrl) URL.revokeObjectURL(posterUrl);
            posterUrl = URL.createObjectURL(file);
            posterPreview.src = posterUrl;
            posterPreview.hidden = false;
            posterPlaceholder.hidden = true;
        });
        posterInput.addEventListener('input', () => posterInput.setCustomValidity(''));

        if (preview.currentSrc || preview.src) {
            preview.addEventListener('loadedmetadata', readDuration, { once: true });
            preview.load();
        }
        window.addEventListener('beforeunload', () => {
            if (previewUrl) URL.revokeObjectURL(previewUrl);
            if (posterUrl) URL.revokeObjectURL(posterUrl);
        });
    }

    document.querySelectorAll('[data-image-form]').forEach(form => {
        const input = form.querySelector('[data-image-input]');
        if (!input) return;
        const dropzone = input.closest('[data-image-dropzone]');
        const preview = document.getElementById(input.dataset.previewTarget);
        const placeholder = form.querySelector('[data-image-placeholder]');
        const currentNote = form.querySelector('[data-image-current-note]');
        const contentPreviewImage = form.querySelector('[data-content-preview-image]');
        const contentPreviewPlaceholder = form.querySelector('[data-content-preview-placeholder]');
        const error = form.querySelector('[data-image-error]');
        let previewUrl = null;

        const showError = message => {
            error.textContent = message;
            error.hidden = false;
        };
        const previewImage = file => {
            error.hidden = true;
            error.textContent = '';
            const extension = file.name.split('.').pop().toLowerCase();
            if (!['png', 'jpg', 'jpeg', 'gif', 'webp'].includes(extension)) {
                showError('Unsupported image format. Choose a PNG, JPG, GIF, or WEBP image.');
                input.value = '';
                return;
            }
            if (file.size === 0) {
                showError('This image is empty. Choose a valid image file.');
                input.value = '';
                return;
            }
            if (file.size > Number(form.dataset.maxImageSize)) {
                showError(`This image exceeds the configured ${form.dataset.maxImageMb} MB limit.`);
                input.value = '';
                return;
            }
            if (previewUrl) URL.revokeObjectURL(previewUrl);
            previewUrl = URL.createObjectURL(file);
            preview.src = previewUrl;
            preview.hidden = false;
            placeholder.hidden = true;
            currentNote.hidden = true;
            if (contentPreviewImage) {
                contentPreviewImage.src = previewUrl;
                contentPreviewImage.hidden = false;
                contentPreviewPlaceholder.hidden = true;
            }
        };

        input.addEventListener('change', () => {
            const file = input.files && input.files[0];
            if (file) previewImage(file);
        });
        form.querySelector('[data-image-browse]').addEventListener('click', event => {
            event.preventDefault();
            input.click();
        });
        ['dragenter', 'dragover'].forEach(type => {
            dropzone.addEventListener(type, event => {
                event.preventDefault();
                dropzone.classList.add('is-dragging');
            });
        });
        ['dragleave', 'drop'].forEach(type => {
            dropzone.addEventListener(type, event => {
                event.preventDefault();
                dropzone.classList.remove('is-dragging');
            });
        });
        dropzone.addEventListener('drop', event => {
            const file = event.dataTransfer.files && event.dataTransfer.files[0];
            if (!file) return;
            const transfer = new DataTransfer();
            transfer.items.add(file);
            input.files = transfer.files;
            previewImage(file);
        });
        window.addEventListener('beforeunload', () => {
            if (previewUrl) URL.revokeObjectURL(previewUrl);
        });

        form.querySelectorAll('[data-preview-source]').forEach(source => {
            const target = form.querySelector(`[data-preview-target-id="${source.dataset.previewTarget}"]`);
            if (!target) return;
            const update = () => {
                const value = source.value.trim();
                if (source.dataset.previewSource === 'product-price') {
                    target.textContent = value && Number.isFinite(Number(value)) ? `$${Number(value).toFixed(2)}` : '';
                } else {
                    target.textContent = value || (
                        source.dataset.previewSource.endsWith('title') ? 'Untitled' :
                        source.dataset.previewSource.endsWith('category') ? 'Uncategorized' :
                        'Description preview'
                    );
                }
            };
            source.addEventListener('input', update);
            update();
        });

        const publishToggle = form.querySelector('[data-content-publish-toggle]');
        const previewStatus = form.querySelector('[data-content-preview-status]');
        if (publishToggle && previewStatus) {
            const updateStatus = () => {
                const active = publishToggle.checked;
                const prefix = publishToggle.name === 'active' ? (active ? 'Active' : 'Inactive') : (active ? 'Published' : 'Draft');
                previewStatus.textContent = `${prefix} preview`;
                previewStatus.classList.toggle('is-published', active);
            };
            publishToggle.addEventListener('change', updateStatus);
            updateStatus();
        }
    });

    document.querySelectorAll('[data-content-upload-form]').forEach(form => {
        const submitButton = form.querySelector('button[type="submit"]');
        const statusPanel = form.querySelector('[data-content-upload-status]');
        const statusTitle = form.querySelector('[data-content-upload-title]');
        const statusMessage = form.querySelector('[data-content-upload-message]');
        const statusIcon = form.querySelector('[data-content-upload-icon]');
        const progress = form.querySelector('[data-content-upload-progress]');
        const progressValue = form.querySelector('[data-content-upload-value]');
        const originalButton = submitButton.innerHTML;
        let submitting = false;

        const setUploadStatus = (state, title, message, icon) => {
            statusPanel.dataset.uploadState = state;
            statusTitle.textContent = title;
            statusMessage.textContent = message;
            statusIcon.innerHTML = `<i class="${icon}" aria-hidden="true"></i>`;
        };

        form.addEventListener('submit', event => {
            event.preventDefault();
            if (submitting || !form.reportValidity()) return;
            submitting = true;
            submitButton.disabled = true;
            submitButton.innerHTML = '<i class="ri-loader-4-line" aria-hidden="true"></i> Saving…';
            progress.hidden = false;
            progressValue.hidden = false;
            progress.value = 0;
            progressValue.textContent = '0%';
            setUploadStatus('uploading', 'Uploading changes', 'Sending your content and image securely…', 'ri-upload-cloud-2-line');

            const xhr = new XMLHttpRequest();
            xhr.open('POST', form.action);
            xhr.withCredentials = true;
            xhr.upload.addEventListener('progress', uploadEvent => {
                if (!uploadEvent.lengthComputable) return;
                const percentage = Math.min(95, Math.round(uploadEvent.loaded / uploadEvent.total * 95));
                progress.value = percentage;
                progressValue.textContent = `${percentage}%`;
                if (uploadEvent.loaded >= uploadEvent.total) {
                    setUploadStatus('processing', 'Saving content', 'Media upload is complete. Waiting for the server to validate and save your changes…', 'ri-loader-4-line');
                } else {
                    setUploadStatus('uploading', 'Uploading changes', `Uploading form and media · ${Math.round(uploadEvent.loaded / uploadEvent.total * 100)}%`, 'ri-upload-cloud-2-line');
                }
            });
            xhr.addEventListener('load', () => {
                progress.value = 100;
                progressValue.textContent = '100%';
                const finalUrl = new URL(xhr.responseURL || form.action, window.location.href);
                const formUrl = new URL(form.action, window.location.href);
                if (xhr.status >= 200 && xhr.status < 400 && finalUrl.pathname !== formUrl.pathname && finalUrl.pathname !== '/admin/login') {
                    setUploadStatus('complete', 'Saved successfully', 'Your changes have been saved. Opening the content library…', 'ri-checkbox-circle-line');
                    window.location.assign(finalUrl.href);
                    return;
                }
                const responseDocument = new DOMParser().parseFromString(xhr.responseText, 'text/html');
                const serverMessage = responseDocument.querySelector('.admin-alert-error')?.textContent.trim();
                const message = serverMessage || (xhr.status >= 400
                    ? `The request could not be saved (HTTP ${xhr.status}). Please try again.`
                    : 'The server returned the form without confirming that it was saved. Review the details and try again.');
                setUploadStatus('failed', 'Could not save changes', message, 'ri-error-warning-line');
                submitButton.disabled = false;
                submitButton.innerHTML = originalButton;
                submitting = false;
            });
            xhr.addEventListener('error', () => {
                setUploadStatus('failed', 'Connection error', 'The request could not reach the server. Check your connection and try again.', 'ri-error-warning-line');
                submitButton.disabled = false;
                submitButton.innerHTML = originalButton;
                submitting = false;
            });
            xhr.addEventListener('abort', () => {
                setUploadStatus('failed', 'Save cancelled', 'The save request was cancelled before completion.', 'ri-error-warning-line');
                submitButton.disabled = false;
                submitButton.innerHTML = originalButton;
                submitting = false;
            });
            xhr.send(new FormData(form));
        });
    });

    document.querySelectorAll('[data-video-duration-source]').forEach(video => {
        const duration = video.closest('[data-video-card]').querySelector('[data-video-duration]');
        const updateDuration = () => {
            if (!Number.isFinite(video.duration)) {
                duration.textContent = 'Duration unavailable';
                return;
            }
            const total = Math.floor(video.duration);
            const hours = Math.floor(total / 3600);
            const minutes = Math.floor((total % 3600) / 60);
            const seconds = total % 60;
            duration.textContent = hours
                ? `${hours}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
                : `${minutes}:${String(seconds).padStart(2, '0')}`;
        };
        video.addEventListener('loadedmetadata', updateDuration, { once: true });
        video.addEventListener('error', () => { duration.textContent = 'Duration unavailable'; }, { once: true });
    });

    const videoSearch = document.querySelector('[data-video-search]');
    if (videoSearch) {
        const cards = [...document.querySelectorAll('[data-video-card]')];
        const emptySearch = document.querySelector('[data-video-search-empty]');
        videoSearch.addEventListener('input', () => {
            const query = videoSearch.value.trim().toLowerCase();
            let visibleCards = 0;
            cards.forEach(card => {
                const matches = card.dataset.videoSearchText.includes(query);
                card.hidden = !matches;
                if (matches) visibleCards += 1;
            });
            emptySearch.hidden = visibleCards > 0 || cards.length === 0;
        });
    }

    document.querySelectorAll('[data-content-search]').forEach(search => {
        const cards = [...document.querySelectorAll('[data-content-card]')];
        const emptySearch = document.querySelector('[data-content-search-empty]');
        search.addEventListener('input', () => {
            const query = search.value.trim().toLowerCase();
            let visibleCards = 0;
            cards.forEach(card => {
                const matches = card.dataset.contentSearchText.includes(query);
                card.hidden = !matches;
                if (matches) visibleCards += 1;
            });
            emptySearch.hidden = visibleCards > 0 || cards.length === 0;
        });
    });

    document.querySelectorAll('.admin-alert').forEach(el => {
        setTimeout(() => { el.style.display = 'none'; }, 6000);
    });
});
