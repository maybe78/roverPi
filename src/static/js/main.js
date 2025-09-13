document.addEventListener('DOMContentLoaded', () => {
    const socket = io();

    // Bind JoyStick.js к DIV, а не canvas!
    const joy = new JoyStick('joystickDiv', {}, function(stickData) {
        // stickData.x и .y — значения [-100, 100]
        const lx = (stickData.x / 100).toFixed(2);
        const ly = (-stickData.y / 100).toFixed(2); // Инверсия Y для совместимости

        // Только при движении джойстика шлём не-нулевые значения
        socket.emit('control', { lx, ly });
        console.log(`Sending control: lx=${lx}, ly=${ly}`);
    });

    // Гарантия остановки — когда отпускаем (чтобы робот не уехал вслепую)
    function stopMovement() {
        socket.emit('control', { lx: 0.0, ly: 0.0 });
        console.log('Force stop on touch end');
    }
    document.addEventListener('touchend', stopMovement);
    document.addEventListener('mouseup', stopMovement);
});
