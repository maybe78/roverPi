const socket = io();

const joystick = nipplejs.create({
    zone: document.getElementById('joystick'),
    mode: 'static',
    position: { left: '50%', top: '50%' },
    color: 'blue',
    size: 150
});

joystick.on('move', (evt, data) => {
    if (data && data.vector) {
        // Send axis data to server
        const lx = data.vector.x.toFixed(2);
        const ly = -data.vector.y.toFixed(2); // invert Y

        socket.emit('control', {lx, ly});
        console.log(`Sent control: lx=${lx}, ly=${ly}`);
    }
});

joystick.on('end', () => {
    socket.emit('control', {lx: 0, ly: 0});
    console.log('Joystick released');
});