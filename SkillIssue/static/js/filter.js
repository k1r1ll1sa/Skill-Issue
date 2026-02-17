document.addEventListener('DOMContentLoaded', function() {
    const filterToggle = document.querySelector('.filter-toggle');
    const filterDropdown = document.querySelector('.filter-dropdown');
    const filterItems = document.querySelectorAll('.filter-item');
    const currentFilterText = document.getElementById('current-filter');
    const filterForm = document.querySelector('form[method="GET"]');
    
    let activeFilter = '';
    // Более точное определение страницы
    const pathname = window.location.pathname;
    let isAnnouncementsPage = pathname.includes('/announcements') && !pathname.match(/\/announcements\/\d+/);
    let isGuidesPage = pathname.includes('/guides') && !pathname.match(/\/guides\/\d+/);
    let isMainPage = pathname === '/' || pathname === '' || pathname.match(/^\/$/);
    
    // Если это главная страница или нет формы фильтрации, не выполняем код фильтрации
    if (isMainPage || (!isAnnouncementsPage && !isGuidesPage)) {
        if (isMainPage) {
            console.log('Главная страница, фильтрация не требуется');
        }
        return;
    }
    
    console.log('Определение страницы:', { pathname, isAnnouncementsPage, isGuidesPage });
    
    // Показываем/скрываем меню фильтров
    if (filterToggle) {
        filterToggle.addEventListener('click', function(e) {
            e.stopPropagation();
            const isVisible = filterDropdown.style.display === 'block';
            filterDropdown.style.display = isVisible ? 'none' : 'block';
        });
    }
    
    // Скрываем меню при клике вне его
    document.addEventListener('click', function() {
        if (filterDropdown) {
            filterDropdown.style.display = 'none';
        }
    });
    
    // Обработка выбора фильтра
    if (filterItems.length > 0) {
        filterItems.forEach(item => {
            item.addEventListener('click', function(e) {
                e.stopPropagation();
                e.preventDefault();
                
                // Удаляем активный класс у всех
                filterItems.forEach(i => {
                    i.style.background = 'none';
                    i.style.fontWeight = 'normal';
                });
                
                // Добавляем активный класс к выбранному
                this.style.background = '#f0f0f0';
                this.style.fontWeight = 'bold';
                
                // Обновляем текст на кнопке
                activeFilter = this.getAttribute('data-value') || '';
                if (currentFilterText) {
                    currentFilterText.textContent = this.textContent.trim();
                }
                
                // Закрываем меню
                if (filterDropdown) {
                    filterDropdown.style.display = 'none';
                }

                // Не запускаем запрос немедленно — применится после нажатия "найти"
            });
        });
    }
    
    // Предотвращаем закрытие при клике внутри меню
    if (filterDropdown) {
        filterDropdown.addEventListener('click', function(e) {
            e.stopPropagation();
        });
    }
    
    // Перехватываем отправку формы
    if (filterForm) {
        console.log('Форма найдена, добавляем обработчик submit');
        filterForm.addEventListener('submit', function(e) {
            e.preventDefault();
            console.log('Форма отправлена, вызываем applyFilters');
            applyFilters();
        });
    } else {
        console.error('Форма не найдена! Селектор: form[method="GET"]');
    }
    
    // Применяем фильтры при загрузке страницы, если есть параметры в URL
    const urlParams = new URLSearchParams(window.location.search);
    const hasSearchParams = urlParams.has('search') || urlParams.has('tags') || urlParams.has('date_filter');
    if (hasSearchParams && (isAnnouncementsPage || isGuidesPage)) {
        // Устанавливаем значения из URL в поля формы
        const searchInput = document.querySelector('input[name="search"]');
        const tagsInput = document.querySelector('input[name="tags"]');
        
        if (searchInput && urlParams.has('search')) {
            searchInput.value = urlParams.get('search');
        }
        if (tagsInput && urlParams.has('tags')) {
            tagsInput.value = urlParams.get('tags');
        }
        
        // Устанавливаем фильтр по дате
        if (urlParams.has('date_filter')) {
            const dateFilterValue = urlParams.get('date_filter');
            activeFilter = dateFilterValue;
            
            // Обновляем текст кнопки фильтра
            if (currentFilterText && filterItems.length > 0) {
                filterItems.forEach(item => {
                    if (item.getAttribute('data-value') === dateFilterValue) {
                        currentFilterText.textContent = item.textContent.trim();
                        item.style.background = '#f0f0f0';
                        item.style.fontWeight = 'bold';
                    }
                });
            }
        }
        
        // Применяем фильтры
        applyFilters();
    }
    
    // Функция применения фильтров через API
    function applyFilters() {
        console.log('Применение фильтров...');
        console.log('isAnnouncementsPage:', isAnnouncementsPage);
        console.log('isGuidesPage:', isGuidesPage);
        
        const searchInput = document.querySelector('input[name="search"]');
        const tagsInput = document.querySelector('input[name="tags"]');
        
        const search = searchInput ? searchInput.value.trim() : '';
        const tags = tagsInput ? tagsInput.value.trim() : '';
        const dateFilter = activeFilter;
        
        console.log('Параметры фильтрации:', { search, tags, dateFilter });
        
        // Определяем API endpoint
        let apiUrl = '';
        if (isAnnouncementsPage) {
            apiUrl = '/api/announcements/filter/';
        } else if (isGuidesPage) {
            apiUrl = '/api/guides/filter/';
        } else {
            console.error('Не определена страница (не объявления и не руководства)');
            return;
        }
        
        // Формируем параметры запроса
        const params = new URLSearchParams();
        if (search) params.append('search', search);
        if (tags) params.append('tags', tags);
        const allowedDates = ['today', 'week', 'month'];
        if (dateFilter && allowedDates.includes(dateFilter)) {
            params.append('date_filter', dateFilter);
        }
        
        const url = apiUrl + (params.toString() ? '?' + params.toString() : '');
        console.log('URL запроса:', url);
        
        // Показываем индикатор загрузки
        showLoading();
        
        // Делаем запрос к API
        fetch(url)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                hideLoading();
                console.log('Получены данные:', data);
                console.log('Результаты:', data.results);
                updateResults(data.results || []);
            })
            .catch(error => {
                hideLoading();
                console.error('Ошибка при загрузке данных:', error);
                showError('Произошла ошибка при загрузке данных: ' + error.message);
            });
    }
    
    // Функция обновления результатов на странице
    function updateResults(items) {
        console.log('Обновление результатов, количество:', items.length);
        const scrollArea = document.querySelector('.scroll-area');
        if (!scrollArea) {
            console.error('Не найден элемент .scroll-area');
            return;
        }
        
        let container = scrollArea.querySelector('.profile-row-container');
        if (!container) {
            console.warn('Не найден элемент .profile-row-container, создаем новый');
            container = document.createElement('div');
            container.className = 'profile-row-container';
            container.style = "display: flex; gap: 10px; align-content: flex-start; flex-direction: row; flex-wrap: wrap; justify-content: center;"
            scrollArea.appendChild(container);
        }

        // Очищаем контейнер
        container.innerHTML = '';
        
        if (items.length === 0) {
            const emptyMessage = document.createElement('div');
            emptyMessage.className = 'simple-text';
            emptyMessage.style.cssText = 'text-align: center; width: 100%; padding: 20px;';
            emptyMessage.textContent = 'Ничего не найдено';
            container.appendChild(emptyMessage);
            console.log('Добавлено сообщение "Ничего не найдено"');
            return;
        }
        
        // Добавляем элементы
        items.forEach((item, index) => {
            console.log(`Создание элемента ${index}:`, item);
            try {
                const element = createResultElement(item);
                if (element) {
                    container.appendChild(element);
                    console.log(`Элемент ${index} добавлен`);
                } else {
                    console.error(`Не удалось создать элемент ${index}`);
                }
            } catch (error) {
                console.error(`Ошибка при создании элемента ${index}:`, error);
            }
        });
        console.log('Все элементы добавлены, всего:', container.children.length);
    }
    
    // Функция создания элемента результата
    function createResultElement(item) {
        const div = document.createElement('div');
        div.className = 'guide-element';
        
        const link = document.createElement('a');
        if (isAnnouncementsPage) {
            link.href = `/announcements/${item.id}/`;
        } else {
            link.href = `/guides/${item.id}/`;
        }
        link.style.cssText = 'text-decoration: none; color: inherit; display: flex; flex-direction: column; width: 100%; height: 100%;';
        
        // Изображение
        const img = document.createElement('img');
        img.className = 'image-element';
        if (item.image) {
            // Обрабатываем URL изображения
            img.src = item.image;
            img.onerror = function() {
                // Если изображение не загрузилось, используем дефолтное
                this.src = isAnnouncementsPage ? '/static/images/default-announcement.png' : '/static/images/default-avatar.jpg';
            };
        } else {
            img.src = isAnnouncementsPage ? '/static/images/default-announcement.png' : '/static/images/default-avatar.jpg';
        }
        img.alt = item.title || '';
        link.appendChild(img);
        
        // Название (используем span, так как уже внутри ссылки)
        const title = document.createElement('span');
        title.className = 'simple-text';
        title.style.cssText = 'text-align: center; font-size: 1rem; margin: 0 auto; display: block;';
        title.textContent = item.title || 'Без названия';
        link.appendChild(title);
        
        // Разделитель
        const hr = document.createElement('hr');
        hr.style.width = '90%';
        link.appendChild(hr);
        
        // Автор и рейтинг
        if (isGuidesPage) {
            const authorContainer = document.createElement('div');
            authorContainer.className = 'profile-row-container';
            authorContainer.style.cssText = 'margin: auto; gap:5px';
            
            const author = document.createElement('span');
            author.className = 'text-element';
            author.textContent = item.author_name || item.author || 'Неизвестный автор';
            authorContainer.appendChild(author);
            
            const rating = document.createElement('span');
            rating.className = 'text-element';
            rating.textContent = `${item.rating || 0}★`;
            authorContainer.appendChild(rating);
            
            link.appendChild(authorContainer);
        } else {
            // Для объявлений - просто текст автора (используем span вместо a)
            const author = document.createElement('span');
            author.className = 'simple-text';
            author.style.cssText = 'text-align: center; font-size: 1rem; margin: 0 auto; display: block;';
            author.textContent = item.author || 'Неизвестный автор';
            link.appendChild(author);
        }
        
        div.appendChild(link);
        return div;
    }
    
    // Функция показа индикатора загрузки
    function showLoading() {
        const scrollArea = document.querySelector('.scroll-area');
        if (!scrollArea) return;
        
        const loading = document.createElement('div');
        loading.id = 'filter-loading';
        loading.style.cssText = 'text-align: center; padding: 20px;';
        loading.textContent = 'Загрузка...';
        scrollArea.innerHTML = '';
        scrollArea.appendChild(loading);
    }
    
    // Функция скрытия индикатора загрузки
    function hideLoading() {
        const loading = document.getElementById('filter-loading');
        if (loading) {
            loading.remove();
        }
    }
    
    // Функция показа ошибки
    function showError(message) {
        const scrollArea = document.querySelector('.scroll-area');
        if (!scrollArea) return;
        
        const error = document.createElement('div');
        error.className = 'simple-text';
        error.style.cssText = 'text-align: center; width: 100%; padding: 20px; color: red;';
        error.textContent = message;
        scrollArea.innerHTML = '';
        scrollArea.appendChild(error);
    }
});