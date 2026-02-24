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

                if (response.ok) {
                    if (data.added) {
                        alert('Объявление добавлено в избранное ✓');
                        this.textContent = '★ В избранном';
                    } else {
                        alert('Объявление удалено из избранного');
                        this.textContent = '☆ Добавить в избранное';
                    }
                } else {
                    alert('Ошибка: ' + (data.error || 'Не удалось изменить избранное'));
                }
            } catch (error) {
                console.error('Error:', error);
                alert('Произошла ошибка при работе с избранным');
            }
        });
    }
});