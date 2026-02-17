document.addEventListener('DOMContentLoaded', function () {
    const button = document.getElementById('floating-button');
    const modal = document.getElementById('chat-modal');
    const closeButton = document.getElementById('chat-close-button');
    const backToChats = document.getElementById('back-to-chats');
    const chatContacts = document.getElementById('chat-contacts');
    const chatDialog = document.getElementById('chat-dialog');
    const chatList = document.getElementById('chat-list');
    const profileLink = document.getElementById('profile-link');
    const messagesContainer = document.getElementById('messages-container');
    const messageForm = document.getElementById('message-form');
    const messageInput = document.getElementById('message-input');

    // Превью изображения
    let currentImageFile = null;
    const attachButton = document.getElementById('attach-button');
    const imageUploadInput = document.getElementById('image-upload');
    const imagePreviewContainer = document.getElementById('image-preview-container');
    const imagePreview = document.getElementById('image-preview');
    const removeImageButton = document.getElementById('remove-image');

    if (!modal || !button) return; // Если элементов нет, выходим

    let currentReceiverId = null;
    let contactsCache = {};

    /* ─────────────────────────────────────────────
       ОТКРЫТЬ ОКНО ЧАТА
    ───────────────────────────────────────────── */
    button.addEventListener('click', function () {
        modal.style.right = '20px';
        loadContacts();
    });

    /* ─────────────────────────────────────────────
       ЗАКРЫТЬ ОКНО ЧАТА
    ───────────────────────────────────────────── */
    if (closeButton) {
    closeButton.addEventListener('click', function () {
        modal.style.right = '-400px';
    });
    }


    if (attachButton && imageUploadInput) {
            attachButton.addEventListener('click', () => {
            imageUploadInput.click();
        });

        imageUploadInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (!file) return;

            // Проверка типа файла
            if (!file.type.match('image.*')) {
                alert('Пожалуйста, выберите изображение (PNG, JPG, JPEG)');
                imageUploadInput.value = '';
                return;
            }

            // Проверка размера (опционально, например до 5МБ)
            if (file.size > 5 * 1024 * 1024) {
                alert('Размер изображения не должен превышать 5 МБ');
                imageUploadInput.value = '';
                return;
            }

            // Создание превью
            const reader = new FileReader();
            reader.onload = (event) => {
                if (imagePreview) {
                    imagePreview.src = event.target.result;
                    imagePreviewContainer.style.display = 'block';
                    currentImageFile = file;
                    }
                };
                reader.readAsDataURL(file);
            });
        }

        // Удаление изображения из превью
        if (removeImageButton) {
            removeImageButton.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();

                // Сброс всех значений
                if (imagePreview) imagePreview.src = '';
                if (imagePreviewContainer) imagePreviewContainer.style.display = 'none';
                if (imageUploadInput) imageUploadInput.value = '';
                currentImageFile = null;
            });
        }

    /* ─────────────────────────────────────────────
       ЗАГРУЗКА КОНТАКТОВ ИЗ API
    ───────────────────────────────────────────── */
    async function loadContacts() {
        if (!authManager || !authManager.isAuthenticated()) {
            chatList.innerHTML = '<div class="simple-text" style="padding: 20px; color: #666;">Войдите, чтобы использовать чат</div>';
            return;
        }

        try {
            const res = await authManager.apiRequest('/api/chat/contacts/');
            if (!res.ok) throw new Error('Не удалось загрузить контакты');
            
            const contacts = await res.json();
            renderContacts(contacts);
        } catch (err) {
            console.error(err);
            chatList.innerHTML = '<div class="simple-text" style="padding: 20px; color: #c00;">Ошибка загрузки контактов</div>';
        }
    }

    /* ─────────────────────────────────────────────
       ОТОБРАЖЕНИЕ КОНТАКТОВ
    ───────────────────────────────────────────── */
    function renderContacts(contacts) {
        chatList.innerHTML = '';
        contactsCache = {};

        if (contacts.length === 0) {
            chatList.innerHTML = '<div class="simple-text" style="padding: 20px; color: #666;">У вас пока нет сообщений</div>';
            return;
        }

        contacts.forEach(contact => {
            contactsCache[contact.user_id] = contact.username;
            const contactEl = document.createElement('a');
            contactEl.href = '#';
            contactEl.className = 'chat-item';
            contactEl.dataset.userId = contact.user_id;

            const avatarUrl = contact.avatar || '/static/images/default-avatar.jpg';

            contactEl.innerHTML = `
                <img src="${avatarUrl}" alt="Avatar">
                <div style="flex: 1;">
                    <div class="username">${contact.username}</div>
                    <div class="simple-text" style="font-size: 0.85rem; color: #666; margin-top: 3px;">
                        ${contact.last_message || 'Без сообщений'}
                    </div>
                </div>
                ${contact.unread_count > 0 ? `<div style="min-width: 30px; text-align: right; color: #007bff; font-size: 0.8rem;">${contact.unread_count}</div>` : ''}
            `;

            contactEl.addEventListener('click', (e) => {
                e.preventDefault();
                openDialog(contact.user_id, contact.username);
            });

            chatList.appendChild(contactEl);
    });
    }

    /* ─────────────────────────────────────────────
       КНОПКА "НАЗАД"
    ───────────────────────────────────────────── */
    if (backToChats) {
    backToChats.addEventListener('click', function () {
        chatDialog.style.display = 'none';
        chatContacts.style.display = 'flex';
            currentReceiverId = null;
            loadContacts();
        });
    }

    /* ─────────────────────────────────────────────
       ОТКРЫТИЕ ДИАЛОГА
    ───────────────────────────────────────────── */
    async function openDialog(userId, username) {
        if (imagePreviewContainer) imagePreviewContainer.style.display = 'none';
        if (imagePreview) imagePreview.src = '';
        if (imageUploadInput) imageUploadInput.value = '';
        currentImageFile = null;
        if (!authManager || !authManager.isAuthenticated()) {
            alert('Войдите, чтобы использовать чат');
            return;
        }

        chatContacts.style.display = 'none';
        chatDialog.style.display = 'flex';

        profileLink.textContent = username;
        profileLink.href = `/users/${username}/`;

        // Загружаем аватар пользователя
        const dialogAvatar = document.getElementById('dialog-avatar');
        if (dialogAvatar) {
            try {
                const profileRes = await authManager.apiRequest(`/api/profile/${username}/`);
                if (profileRes.ok) {
                    const profile = await profileRes.json();
                    if (profile.avatar) {
                        dialogAvatar.src = profile.avatar;
                    } else {
                        dialogAvatar.src = '/static/images/default-avatar.jpg';
                    }
                } else {
                    dialogAvatar.src = '/static/images/default-avatar.jpg';
                }
            } catch (err) {
                console.error('Ошибка загрузки аватара:', err);
                dialogAvatar.src = '/static/images/default-avatar.jpg';
            }
        }

        currentReceiverId = userId;
        messagesContainer.innerHTML = '<div class="simple-text" style="padding: 20px; color: #666;">Загрузка...</div>';

        try {
            const res = await authManager.apiRequest(`/api/chat/${userId}/messages/`);
            if (!res.ok) throw new Error('Не удалось загрузить сообщения');
            
            const messages = await res.json();
            messagesContainer.innerHTML = '';

            if (messages.length === 0) {
                // Удаляем сообщение "Загрузка..." и добавляем пустое состояние
                const emptyMsg = document.createElement('div');
                emptyMsg.className = 'simple-text';
                emptyMsg.style.cssText = 'padding: 20px; color: #666; text-align: center;';
                emptyMsg.textContent = 'Начните диалог';
                messagesContainer.innerHTML = '';
                messagesContainer.appendChild(emptyMsg);
            } else {
                messagesContainer.innerHTML = '';
                messages.forEach(msg => {
                    addMessage(msg.direction === 'outgoing' ? 'sent' : 'received',
                        msg.message, 
                        formatTime(msg.created_at),
                        msg.image_url
                    );
                });
            }
        } catch (err) {
            console.error(err);
            messagesContainer.innerHTML = '<div class="simple-text" style="padding: 20px; color: #c00;">Ошибка загрузки сообщений</div>';
        }
    }

    /* ─────────────────────────────────────────────
       ДОБАВЛЕНИЕ СООБЩЕНИЯ
    ───────────────────────────────────────────── */
    function addMessage(type, text, time, imageUrl = null) {
        if (!messagesContainer) {
            console.error('Контейнер сообщений не найден при добавлении сообщения');
            return;
        }

        // Удаляем сообщение "Начните диалог" если оно есть
        const emptyMsg = messagesContainer.querySelector('.simple-text');
        if (emptyMsg && emptyMsg.textContent.includes('Начните диалог')) {
            emptyMsg.remove();
        }

        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}`;
        messageDiv.style.cssText = type === 'sent'
            ? "max-width: 70%; background: #007bff; color: white; padding: 10px 15px; border-radius: 18px 18px 4px 18px; align-self: flex-end; box-shadow: 0 1px 3px rgba(0,0,0,0.1);"
            : "max-width: 70%; background: white; padding: 10px 15px; border-radius: 18px 18px 18px 4px; align-self: flex-start; box-shadow: 0 1px 3px rgba(0,0,0,0.1);";

        let content = '';

        // Добавляем изображение, если есть
        if (imageUrl) {
            content += `
                <div style="max-width: 100%; margin-bottom: ${text ? '8px' : '0'};">
                    <img src="${imageUrl}" alt="Изображение" 
                         style="max-width: 100%; max-height: 400px; border-radius: 8px; display: block; cursor: pointer;"
                         onclick="window.open('${imageUrl}', '_blank')">
                </div>
            `;
        }

        // Добавляем текст, если есть
        if (text) {
            content += `
                <div class="message-text" style="font-size: 0.95rem; ${type === 'sent' ? 'color: white;' : 'color: #333;'}">
                    ${escapeHtml(text)}
                </div>
            `;
        }

        // Добавляем время
        content += `
            <div class="message-time" style="font-size: 0.75rem; ${type === 'sent' ? 'color: rgba(255,255,255,0.8);' : 'color: #999;'} text-align: right; margin-top: 4px;">
                ${time}
            </div>
        `;

        messageDiv.innerHTML = content;
        messagesContainer.appendChild(messageDiv);
        
        // Проверяем, что сообщение действительно добавлено
        const addedMessage = messagesContainer.querySelector(`.message.${type}:last-child`);
        if (!addedMessage) {
            console.error('Сообщение не было добавлено в DOM!');
        } else {
            console.log('Сообщение успешно добавлено в DOM:', addedMessage);
        }
        
        // Прокручиваем вниз
        requestAnimationFrame(() => {
            if (messagesContainer) {
                messagesContainer.scrollTop = messagesContainer.scrollHeight;
                console.log('Прокрутка выполнена, scrollTop:', messagesContainer.scrollTop, 'scrollHeight:', messagesContainer.scrollHeight);
            }
        });

        console.log('Сообщение добавлено в интерфейс:', { 
            type, 
            text, 
            time, 
            containerExists: !!messagesContainer,
            containerChildren: messagesContainer.children.length 
        });
    }

    /* ─────────────────────────────────────────────
       ФОРМАТИРОВАНИЕ ВРЕМЕНИ
    ───────────────────────────────────────────── */
    function formatTime(dateStr) {
        const date = new Date(dateStr);
        return date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
    }

    /* ─────────────────────────────────────────────
       ЭКРАНИРОВАНИЕ HTML
    ───────────────────────────────────────────── */
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /* ─────────────────────────────────────────────
       ОТПРАВКА СООБЩЕНИЯ (делегирование событий)
    ───────────────────────────────────────────── */
    // Используем делегирование событий на modal, чтобы обработчик работал всегда
    if (modal) {
        console.log('Инициализация обработчика формы сообщения');
        
        modal.addEventListener('submit', async function(e) {
            console.log('Событие submit перехвачено:', e.target);
            
            // Проверяем, что это наша форма сообщения
            if (e.target.id !== 'message-form') {
                console.log('Это не форма сообщения, игнорируем');
                return;
            }
            
            e.preventDefault();
            e.stopPropagation();
            
            console.log('Форма отправки сообщения вызвана');    
            
            const input = document.getElementById('message-input');
            if (!input) {
                console.error('Поле ввода сообщения не найдено');
                return false;
            }
            
            if (!currentReceiverId) {
                alert('Сначала выберите собеседника');
                return false;
            }

            const text = input.value.trim();
            const hasImage = !!currentImageFile;
            if (!text && !hasImage) {
                console.log('Сообщение должно содержать текст или изображение');
                return false;
            }

            if (!authManager || !authManager.isAuthenticated()) {
                alert('Войдите, чтобы отправить сообщение');
                return false;
            }

            const formData = new FormData();
            formData.append('receiver_id', currentReceiverId);
            if (text) {
                formData.append('message', text);
            }
            if (hasImage) {
                formData.append('image', currentImageFile);
            }

            // Блокируем повторную отправку
            const submitBtn = e.target.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.disabled = true;
            }

            try {
                console.log('Отправка сообщения:', { receiver_id: currentReceiverId, message: text });
                
                const res = await authManager.apiRequest('/api/chat/send/', {
                    method: 'POST',
                    body: formData,
                });

                console.log('Ответ сервера:', res.status, res.statusText);

                if (!res.ok) {
                    const errorData = await res.json().catch(() => ({}));
                    console.error('Ошибка отправки:', errorData);
                    throw new Error(errorData.error || 'Не удалось отправить сообщение');
                }

                const data = await res.json();
                console.log('Сообщение отправлено, данные:', data);
                
                // Очищаем поле ввода
                input.value = '';
                if (imagePreviewContainer) imagePreviewContainer.style.display = 'none';
                if (imagePreview) imagePreview.src = '';
                if (imageUploadInput) imageUploadInput.value = '';
                currentImageFile = null;
                
                // Проверяем, что контейнер сообщений существует и диалог открыт
                const messagesContainer = document.getElementById('messages-container');
                if (!messagesContainer) {
                    console.error('Контейнер сообщений не найден!');
                    alert('Ошибка: контейнер сообщений не найден');
                    return;
                }

                // Проверяем, что диалог открыт
                const chatDialog = document.getElementById('chat-dialog');
                if (chatDialog && chatDialog.style.display === 'none') {
                    console.warn('Диалог закрыт, открываем...');
                    chatDialog.style.display = 'flex';
                }
                
                // Добавляем сообщение в интерфейс
                const messageText = data.message || text;
                const imageUrl = data.image_url;
                const messageTime = data.created_at ? formatTime(data.created_at) : formatTime(new Date().toISOString());
                
                console.log('Добавляем сообщение в интерфейс:', { messageText, messageTime, containerExists: !!messagesContainer });
                addMessage('sent', messageText, messageTime, imageUrl);
                
                // Обновляем список контактов
                await loadContacts();
            } catch (err) {
                console.error('Ошибка отправки сообщения:', err);
                alert(err.message || 'Ошибка при отправке сообщения');
            } finally {
                // Разблокируем кнопку
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = '↵';
                }
            }
            
            return false;
        }, true); // Используем capture phase
        
        // Также добавляем обработчик на клик по кнопке (на случай если форма не срабатывает)
        modal.addEventListener('click', async function(e) {
            const btn = e.target.closest('button[type="submit"]');
            if (btn && btn.closest('#message-form')) {
                e.preventDefault();
                e.stopPropagation();
                
                console.log('Клик по кнопке отправки перехвачен');
                
                const form = btn.closest('#message-form');
                const input = form ? form.querySelector('#message-input') : null;
                
                if (!form || !input) {
                    console.error('Форма или поле ввода не найдены');
                    return;
                }
                
                if (!currentReceiverId) {
                    alert('Сначала выберите собеседника');
                    return;
                }

                if (!authManager || !authManager.isAuthenticated()) {
                    alert('Войдите, чтобы отправить сообщение');
                    return;
                }

                // Вызываем обработчик формы программно
                const submitEvent = new Event('submit', { bubbles: true, cancelable: true });
                form.dispatchEvent(submitEvent);
            }
        });
    }

    /* ─────────────────────────────────────────────
       СОЗДАНИЕ / ОТКРЫТИЕ ЧАТА ИЗ КНОПКИ "НАПИСАТЬ"
    ───────────────────────────────────────────── */
    const writeBtn = document.getElementById("write-message");

    if (writeBtn) {
        writeBtn.addEventListener("click", function () {
            const userId = this.dataset.userId;
            const username = this.dataset.username;
            
            if (!authManager || !authManager.isAuthenticated()) {
                alert('Войдите, чтобы использовать чат');
                return;
            }
            
            openChatWithUser(userId, username);
        });
    }

    async function openChatWithUser(userId, username) {
        // Открыть окно чата
        modal.style.right = "20px";

        // Загрузить контакты
        await loadContacts();

        // Проверить, есть ли контакт в списке
        let existing = chatList.querySelector(`[data-user-id="${userId}"]`);

        if (!existing) {
            // Создать новый контакт в списке
            const contact = document.createElement("a");
            contact.href = "#";
            contact.className = "chat-item";
            contact.dataset.userId = userId;

            contact.innerHTML = `
                <img src="/static/images/default-avatar.jpg" alt="Avatar">
                <div style="flex: 1;">
                    <div class="username">${username}</div>
                    <div class="simple-text" style="font-size: 0.85rem; color: #666; margin-top: 3px;">Начните диалог</div>
                </div>
            `;

            contact.addEventListener("click", (e) => {
                e.preventDefault();
                openDialog(userId, username);
            });

            chatList.prepend(contact);
            contactsCache[userId] = username;
        }

        // Открыть диалог
        openDialog(userId, username);
    }

    // Загрузить контакты при открытии страницы (если пользователь авторизован)
    if (authManager && authManager.isAuthenticated()) {
        loadContacts();
    }
});
