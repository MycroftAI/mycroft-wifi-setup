var WS = {
    ws: null,
    listeners: {},
    onOpenListeners: [],

    connect: function () {
        this.ws = new WebSocket(Config.wsUrl);
        this.ws.onmessage = this.onMessage.bind(this);
        this.ws.onopen = this.onOpen.bind(this);
    },

    setOnOpenListener: function (cb) {
        this.onOpenListener = cb;
    },

    onMessage: function (evt) {
        var msg = JSON.parse(evt.data);
        if (this.listeners[msg.type]) {
            this.listeners[msg.type].forEach(function (cb) {
                cb(msg.data);
            });
        }
    },

    onOpen: function () {
        this.onOpenListener();
    },

    send: function (type, data) {
        this.ws.send(JSON.stringify({
            type: type,
            data: data
        }));
    },

    close: function () {
        this.ws.close();
        this.ws = null;
    },

    addMessageListener: function (type, callback) {
        this.listeners[type] = this.listeners[type] || [];
        this.listeners[type].push(callback);
    }

};
