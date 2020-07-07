/*
 * application main component
 */
import App from './js/components/App.vue';
//Vue.config.productionTip = false;
//Vue.use(Vuex);
// /*
//  * use state variables, e.g. patient id, project id,  for access globally
//  * can set other variables when need to 
//  */
// const store = new Vuex.Store({
//     state: {
//         userId: 0,
//         settings: {},
//         locale: 'en'
//     },
//     mutations: {
//         setUserId (state, payload) {
//             state.userId = payload;
//         },
//         setSettings (state, payload) {
//             if (payload) {
//                 state.settings = payload;
//             }
//         },
//         setSettings (state, payload) {
//             if (payload) {
//                 state.locale = payload;
//             }
//         },
//     }
// });
var SubStudyAppObj = window.SubStudyAppObj = new Vue({ /*global Vue $ */
    el: "#app",
    render: h => h(App)
}).$mount("#app");


