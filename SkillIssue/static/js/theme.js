// Глобальная функция для переключения темы
window.toggleTheme = function(e) {
    if (e) {
        e.preventDefault();
        e.stopPropagation();
    }
    
    const html = document.documentElement;
    const currentTheme = html.getAttribute('data-theme') || 'light';
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    
    html.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    
    // Обновляем иконку кнопки
    updateThemeIcon(newTheme);
    
    console.log('Theme switched to:', newTheme);
};

// Функция для обновления иконки кнопки темы
function updateThemeIcon(theme) {
    const themeToggle = document.getElementById('theme-toggle');
    if (themeToggle) {
        themeToggle.textContent = theme === 'dark' ? '☀️' : '🌙';
        themeToggle.title = theme === 'dark' ? 'Переключить на светлую тему' : 'Переключить на темную тему';
    }
}

// Инициализация темы при загрузке страницы
function initTheme() {
    // Проверяем сохраненную тему в localStorage или используем светлую по умолчанию
    const savedTheme = localStorage.getItem('theme') || 'light';
    const html = document.documentElement;
    html.setAttribute('data-theme', savedTheme);
    
    // Обновляем иконку кнопки
    updateThemeIcon(savedTheme);
    
    // Добавляем обработчик события для кнопки переключения темы
    const themeToggle = document.getElementById('theme-toggle');
    if (themeToggle) {
        // Удаляем старый обработчик, если есть
        themeToggle.removeEventListener('click', window.toggleTheme);
        // Добавляем новый обработчик
        themeToggle.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            window.toggleTheme();
        });
    }
}

// Инициализация при загрузке DOM
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initTheme);
} else {
    // DOM уже загружен
    initTheme();
}

// Также инициализируем при полной загрузке страницы
window.addEventListener('load', function() {
    // Повторная инициализация на случай, если кнопка была создана динамически
    setTimeout(initTheme, 100);
});

