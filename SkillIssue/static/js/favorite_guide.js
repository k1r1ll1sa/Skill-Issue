document.addEventListener('DOMContentLoaded', function() {
    const favoriteBtn = document.getElementById('add-favorite');

    if (favoriteBtn) {
        favoriteBtn.addEventListener('click', async function(e) {
            e.preventDefault();

            const guideId = this.dataset.guideId;
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
                             document.cookie.split('; ').find(row => row.startsWith('csrftoken='))?.split('=')[1];

            try {
                const response = await fetch(`/guides/${guideId}/toggle-favorite/`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken
                    },
                    body: JSON.stringify({
                        guide_id: guideId
                    })
                });

                const data = await response.json();
                const lang = localStorage.getItem('lang') || 'RU';

                if (response.ok) {
                    if (data.added) {
                        const msg = lang === 'RU'
                            ? 'Руководство добавлено в избранное ✓'
                            : 'Guide added to favorites ✓';
                        alert(msg);
                        this.classList.add('favorite-btn--active');
                        this.dataset.langRu = '★ В избранном';
                        this.dataset.langEn = '★ In favorites';
                        this.textContent = lang === 'RU' ? this.dataset.langRu : this.dataset.langEn;
                    } else {
                        const msg = lang === 'RU'
                            ? 'Руководство удалено из избранного'
                            : 'Guide removed from favorites';
                        alert(msg);
                        this.classList.remove('favorite-btn--active');
                        this.dataset.langRu = '☆ Добавить в избранное';
                        this.dataset.langEn = '☆ Add to favorites';
                        this.textContent = lang === 'RU' ? this.dataset.langRu : this.dataset.langEn;
                    }
                } else {
                    const baseError = data.error || 'Не удалось изменить избранное';
                    const msg = lang === 'RU'
                        ? `Ошибка: ${baseError}`
                        : `Error: ${baseError}`;
                    alert(msg);
                }
            } catch (error) {
                const lang = localStorage.getItem('lang') || 'RU';
                const msg = lang === 'RU'
                    ? 'Произошла ошибка при работе с избранным'
                    : 'An error occurred while processing favorites';
                alert(msg);
            }
        });
    }
});