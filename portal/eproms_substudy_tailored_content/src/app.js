/*
 * application main component
 */
import Vue from 'vue';
import App from './components/App.vue';
import VueRouter from 'vue-router';

Vue.use(VueRouter);

const router = new VueRouter({
    routes: [
        { path: "/", component: App},
        { path: "/:topic", component: App }
    ]
})

const app  = new Vue({ /*global Vue $ */
    el: "#app",
    render: h => h(App),
    router,
}).$mount("#app");

export default router;