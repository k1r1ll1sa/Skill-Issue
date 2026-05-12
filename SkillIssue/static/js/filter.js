document.addEventListener('DOMContentLoaded', function() {
    const slider = document.getElementById('daysRangeSlider');
    const valueDisplay = document.getElementById('daysRangeValue');
    const filterForm = document.querySelector('form[method="GET"]');
    
    let activeFilter = '';
    // Более точное определение страницы
    const pathname = window.location.pathname;
    let isAnnouncementsPage = pathname.includes('/announcements') && !pathname.match(/\/announcements\/\d+/);
    let isGuidesPage = pathname.includes('/guides') && !pathname.match(/\/guides\/\d+/);
    let isMainPage = pathname === '/' || pathname === '' || pathname.match(/^\/$/);
    
    // Если это главная страница или нет формы фильтрации, не выполняем код фильтрации
    if (isMainPage || (!isAnnouncementsPage && !isGuidesPage)) {
        return;
    }
    
    // Функция склонения слов (день, дня, дней)
    function getDaysText(n) {
        if (n % 10 === 1 && n % 100 !== 11) return n + ' день';
        if (n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20)) return n + ' дня';
        return n + ' дней';
    }
    
    // Функция обновления текста ползунка
    function updateSliderValue() {
        const days = slider.value;
        valueDisplay.textContent = getDaysText(days);
        activeFilter = days;
    }

    // Обработчик изменения ползунка
    if (slider && valueDisplay) {
        slider.addEventListener('input', updateSliderValue);
        updateSliderValue(); // инициализация
    }
    
    // Перехватываем отправку формы
    if (filterForm) {
        console.log('Форма найдена, добавляем обработчик submit');
        filterForm.addEventListener('submit', function(e) {
            e.preventDefault();
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

            if (daysSlider) {
                daysSlider.value = daysValue;
            }
            if (sliderValue) {
                sliderValue.textContent = `${daysValue} ${getDaysText(daysValue)}`;
            }

            activeFilter = dateFilterValue;
        }
        
        // Применяем фильтры
        applyFilters();
    }
    
    // Функция применения фильтров через API
    function applyFilters() {
        const searchInput = document.querySelector('input[name="search"]');
        const tagsInput = document.querySelector('input[name="tags"]');
        const search = searchInput ? searchInput.value.trim() : '';
        const tags = tagsInput ? tagsInput.value.trim() : '';
        const dateFilter = activeFilter;
        
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
        if (dateFilter && !isNaN(dateFilter) && dateFilter > 0) {
            params.append('date_filter', dateFilter);
        }
        
        const url = apiUrl + (params.toString() ? '?' + params.toString() : '');
        
        // Показываем индикатор загрузки
        showLoading();
        
        // Делаем запрос к API
        fetch(url)
            .then(response => {
                if (!response.ok) {
                    console.log(response)
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
    
    // Находим первый feed-grid на странице (секция результатов/популярного)
    function getGrid() {
        return document.querySelector('.feed-grid');
    }

    // Функция обновления результатов на странице
    function updateResults(items) {
        const grid = getGrid();
        if (!grid) {
            console.error('Не найден элемент .feed-grid');
            return;
        }

        grid.innerHTML = '';

        if (items.length === 0) {
            const empty = document.createElement('div');
            empty.className = 'feed-empty';
            empty.innerHTML = '<div class="feed-empty-icon">📭</div>'
                + '<p class="feed-empty-title">Ничего не найдено</p>'
                + '<p class="feed-empty-sub">Попробуйте другой запрос или сбросьте фильтры</p>';
            grid.appendChild(empty);
            return;
        }

        items.forEach((item, index) => {
            try {
                const card = createResultElement(item);
                if (card) {
                    card.style.animationDelay = (index * 0.05) + 's';
                    grid.appendChild(card);
                }
            } catch (err) {
                console.error(`Ошибка при создании карточки ${index}:`, err);
            }
        });
    }

    // Функция создания карточки в новом дизайне (.feed-card)
    function createResultElement(item) {
        const defaultImg = isAnnouncementsPage
            ? '/static/images/default-announcement.png'
            : '/static/images/default-guide.png';

        const href = isAnnouncementsPage
            ? `/announcements/${item.id}/`
            : `/guides/${item.id}/`;

        const imgSrc = item.image || defaultImg;
        const authorName = item.author_name || item.author || 'Неизвестный автор';
        const rating = item.rating !== undefined ? item.rating : null;

        const article = document.createElement('article');
        article.className = 'feed-card';

        article.innerHTML = `
            <a class="feed-card-link" href="${href}">
                <div class="feed-card-thumb">
                    <img class="feed-card-img"
                         src="${imgSrc}"
                         alt="${item.title || ''}"
                         loading="lazy"
                         onerror="this.src='${defaultImg}'">
                </div>
                <div class="feed-card-body">
                    <p class="feed-card-title">${item.title || 'Без названия'}</p>
                    <div class="feed-card-divider"></div>
                    <div class="feed-card-meta">
                        <div class="feed-card-author">
                            <span class="feed-card-author-name">${authorName}</span>
                        </div>
                        ${rating !== null && isGuidesPage
                            ? `<div class="feed-card-rating">
                                   <span class="feed-card-star">★</span>${rating}
                               </div>`
                            : ''}
                    </div>
                </div>
            </a>`;

        return article;
    }

    // Функция показа индикатора загрузки
    function showLoading() {
        const grid = getGrid();
        if (!grid) return;

        grid.innerHTML = Array.from({ length: 4 }, () => `
            <div class="feed-skeleton">
                <div class="feed-skeleton-thumb"></div>
                <div class="feed-skeleton-body">
                    <div class="feed-skeleton-line feed-skeleton-line--long"></div>
                    <div class="feed-skeleton-line feed-skeleton-line--medium"></div>
                    <div class="feed-skeleton-line feed-skeleton-line--short"></div>
                </div>
            </div>`).join('');
    }

    // Функция скрытия индикатора загрузки
    function hideLoading() {
        const grid = getGrid();
        if (!grid) return;
        grid.querySelectorAll('.feed-skeleton').forEach(el => el.remove());
    }

    // Функция показа ошибки
    function showError(message) {
        const grid = getGrid();
        if (!grid) return;

        grid.innerHTML = `
            <div class="feed-empty" style="grid-column:1/-1">
                <div class="feed-empty-icon">⚠️</div>
                <p class="feed-empty-title">Ошибка загрузки</p>
                <p class="feed-empty-sub">${message}</p>
            </div>`;
    }
});