document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('searchInput');
    const searchDropdown = document.getElementById('searchDropdown');

    // Проверяем наличие элементов поиска
    if (!searchInput || !searchDropdown) {
        console.warn('Элементы поиска не найдены на странице');
        return;
    }

    let allSearchData = [];
    let dataLoaded = false;

    // Загрузка всех данных при фокусе
    searchInput.addEventListener('focus', async function() {
        if (!dataLoaded && allSearchData.length === 0) {
            await loadAllSearchData();
        }
    });

    async function loadAllSearchData() {
        try {
            const response = await fetch('/api/search/all/');
            if (response.ok) {
                allSearchData = await response.json();
                dataLoaded = true;
            }
        } catch (error) {
            console.error('Ошибка загрузки данных:', error);
        }
    }

    // Поиск с debounce
    let searchTimeout;
    searchInput.addEventListener('input', function() {
        clearTimeout(searchTimeout);
        const query = this.value.trim();

        searchTimeout = setTimeout(() => {
            if (query.length > 0) {
                if (dataLoaded) {
                    performLocalSearch(query);
                } else {
                    performAPISearch(query);
                }
            } else {
                searchDropdown.classList.remove('active');
            }
        }, 300);
    });

    function performLocalSearch(query) {
        const results = allSearchData.filter(item =>
            item.title.toLowerCase().includes(query.toLowerCase())
        );
        displayResults(results);
    }

    async function performAPISearch(query) {
        try {
            const response = await fetch(`/api/search/?q=${encodeURIComponent(query)}`);
            if (response.ok) {
                const results = await response.json();
                displayResults(results);
            }
        } catch (error) {
            console.error('Ошибка поиска:', error);
        }
    }

    function displayResults(results) {
        searchDropdown.innerHTML = '';

        if (results.length > 0) {
            results.forEach(item => {
                const itemElement = createSearchItem(item);
                searchDropdown.appendChild(itemElement);
            });
            searchDropdown.classList.add('active');
        } else {
            const noResults = document.createElement('div');
            noResults.className = 'search-dropdown-item';
            noResults.textContent = 'Ничего не найдено';
            searchDropdown.appendChild(noResults);
            searchDropdown.classList.add('active');
        }
    }

    function createSearchItem(item) {
        const itemElement = document.createElement('div');
        itemElement.className = 'search-dropdown-item';

        itemElement.innerHTML = `
            <div style="font-weight: bold; margin-bottom: 2px;">${item.title}</div>
            <div style="font-size: 0.8em; color: #666;">${getTypeLabel(item.type)}</div>
        `;

        itemElement.addEventListener('click', function() {
            window.location.href = item.url;
        });

        itemElement.addEventListener('mouseenter', function() {
            this.style.backgroundColor = '#f5f5f5';
        });

        itemElement.addEventListener('mouseleave', function() {
            this.style.backgroundColor = '';
        });

        return itemElement;
    }

    function getTypeLabel(type) {
        const typeLabels = {
            'руководство': 'Руководство',
            'объявление': 'Объявление',
            'профиль': 'Профиль'
        };
        return typeLabels[type] || type;
    }

    // Закрытие dropdown при клике вне области
    document.addEventListener('click', function(event) {
        if (!searchInput.contains(event.target) && !searchDropdown.contains(event.target)) {
            searchDropdown.classList.remove('active');
        }
    });

    // Обработка клавиши Escape
    searchInput.addEventListener('keydown', function(event) {
        if (event.key === 'Escape') {
            searchDropdown.classList.remove('active');
        }
    });
});
