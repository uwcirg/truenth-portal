import Vue from 'vue';
import VueRouter from 'vue-router';
import App from '../components/App.vue';

Vue.use(VueRouter);

const router = new VueRouter({
    routes: [
        { path: "/", component: App},
        { path: "/:topic", component: App }
    ]
});

export default router;

