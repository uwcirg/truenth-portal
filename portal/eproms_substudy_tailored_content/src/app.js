/*
 * application main component
 */
import Vue from 'vue';
import App from './components/App.vue';
import router from './js/Router';

const app  = new Vue({ /*global Vue $ */
    el: "#app",
    render: h => h(App),
    router,
}).$mount("#app");

