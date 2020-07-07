/*
 * application main component
 */
import App from './js/components/App.vue';
var SubStudyAppObj = window.SubStudyAppObj = new Vue({ /*global Vue $ */
    el: "#app",
    render: h => h(App)
}).$mount("#app");



