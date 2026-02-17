// Утилита для работы с JWT токенами и аутентификацией

class AuthManager {
    constructor() {
        this.accessTokenKey = 'access_token';
        this.refreshTokenKey = 'refresh_token';
        this.userKey = 'user_data';
    }

    // Сохранение токенов в localStorage
    setTokens(accessToken, refreshToken, userData = null) {
        localStorage.setItem(this.accessTokenKey, accessToken);
        localStorage.setItem(this.refreshTokenKey, refreshToken);
        if (userData) {
            localStorage.setItem(this.userKey, JSON.stringify(userData));
        }
    }

    // Получение access токена
    getAccessToken() {
        return localStorage.getItem(this.accessTokenKey);
    }

    // Получение refresh токена
    getRefreshToken() {
        return localStorage.getItem(this.refreshTokenKey);
    }

    // Получение данных пользователя
    getUserData() {
        const userData = localStorage.getItem(this.userKey);
        return userData ? JSON.parse(userData) : null;
    }

    // Проверка, авторизован ли пользователь
    isAuthenticated() {
        return !!this.getAccessToken();
    }

    // Очистка токенов
    clearTokens() {
        localStorage.removeItem(this.accessTokenKey);
        localStorage.removeItem(this.refreshTokenKey);
        localStorage.removeItem(this.userKey);
    }

    // Получение заголовков с токеном для API запросов
    getAuthHeaders() {
        const token = this.getAccessToken();
        const headers = {
            'Content-Type': 'application/json',
        };

        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }
        
        return headers;
    }

    // Обновление access токена
    async refreshAccessToken() {
        const refreshToken = this.getRefreshToken();
        if (!refreshToken) {
            throw new Error('No refresh token available');
        }

        try {
            const response = await fetch('/api/token/refresh/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ refresh: refreshToken }),
            });

            if (!response.ok) {
                throw new Error('Failed to refresh token');
            }

            const data = await response.json();
            localStorage.setItem(this.accessTokenKey, data.access);
            return data.access;
        } catch (error) {
            this.clearTokens();
            throw error;
        }
    }

    // Выполнение API запроса с автоматическим обновлением токена при необходимости
    async apiRequest(url, options = {}) {
        const headers = {
            ...this.getAuthHeaders(),
            ...(options.headers || {}),
        };

        if (options.body instanceof FormData) {
            delete headers['Content-Type'];
        };
        
        let response = await fetch(url, {
            ...options,
            headers,
        });

        // Если токен истек, пытаемся обновить
        if (response.status === 401 && this.getRefreshToken()) {
            try {
                await this.refreshAccessToken();
                // Повторяем запрос с новым токеном
                headers['Authorization'] = `Bearer ${this.getAccessToken()}`;
                response = await fetch(url, {
                    ...options,
                    headers,
                });
            } catch (error) {
                // Если не удалось обновить токен, перенаправляем на страницу входа
                this.clearTokens();
                window.location.href = '/login-page/';
                throw error;
            }
        }

        return response;
    }

    // Выход из системы
    logout() {
        this.clearTokens();
        fetch('/logout/', {
            method: 'GET',
            credentials: 'include'
        }).finally(() => {
            window.location.href = '/';
        });
    }
}

// Создаем глобальный экземпляр
const authManager = new AuthManager();

// Функция для получения CSRF токена
function getCSRFToken() {
    const metaTag = document.querySelector('meta[name="csrf-token"]');
    if (metaTag) {
        return metaTag.getAttribute('content');
    }
    
    // Альтернативный способ через cookie
    const name = 'csrftoken';
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.startsWith(name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

