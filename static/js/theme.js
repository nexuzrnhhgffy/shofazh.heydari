document.addEventListener('DOMContentLoaded', function(){
    const root = document.documentElement;
    const buttons = document.querySelectorAll('.color-btn');
    buttons.forEach(btn=>{
        btn.addEventListener('click', ()=>{
            const main = btn.dataset.main;
            const main2 = btn.dataset.main2 || main;
            root.style.setProperty('--main', main);
            root.style.setProperty('--main-2', main2);
            buttons.forEach(b=>b.classList.remove('active'));
            btn.classList.add('active');
        });
    });
});