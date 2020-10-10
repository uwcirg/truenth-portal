import {checkIE, isInViewport, getUrlParameter, tryParseJSON} from "./Utility";
export default {
    mounted: function() {
        Promise.all([
            this.$http(this.settingsURL).catch(error => { return error }),
            this.$http(this.meURL).catch(error => { return error }),
        ]).then(responses => {
            try {
                this.setSettings(JSON.parse(responses[0]));
            } catch(e) {
                this.setErrorMessage(`Error parsing data ${e}`);
            }
            try {
                this.userInfo = JSON.parse(responses[1]);
            } catch(e) {
                this.setErrorMessage(`Error parsing data ${e}`);
            }
            this.initApp();
            console.log("settings? ", this.settings);
            console.log("user? ", this.userInfo)
        }).catch(error => {
            this.setErrorMessage(`Error in promises ${error}`);
            this.initApp();
        });
    },
    /*
     * methods available to the application
     */
    methods: {
        isLoading() {
            return this.loading;
        },
        isInitialized() {
            return this.initialized;
        },
        initApp() {
           // let self = this;
            this.setSettings(this.settings);
            this.setLRBaseURL(this.settings?this.settings["LR_ORIGIN"]:"");
            this.setUserID(this.userInfo?this.userInfo["id"]:0);
            this.initialized = true;
            Promise.all([
                 //TODO init user domains, call api based on user id
                this.$http(`/api/demographics/${this.getUserID()}`).catch(error => { return error }),
            ]).then(responses => {
                try {
                    this.setLocale(JSON.parse(responses[0]));
                } catch(e) {
                    this.setErrorMessage(`Error parsing data ${e}`);
                }
                console.log("user locale? ", this.getLocale())
                //get welcome page
                //TODO filter content based on user's domains?
                //each domain link on the intro/welcome page should have a representative attribute or css class
                this.setSelectedDomain();
                //that denote which domain it represents
                this.getDomainContent();
               // self.setInitView();
            }).catch(error => {
                this.setErrorMessage(`Error in promises ${error}`);
                this.setInitView();
            });
        },
        setInitView() {
            //let self = this;
            Vue.nextTick(() => {
                    setTimeout(function() {
                        this.setCurrentView("domain");
                        this.loading = false;
                    }.bind(this), 350);
                }
            );
        },
        hasError() {
            return this.errorMessage !== "";
        },
        resetError() {
            this.setErrorMessage("");
        },
        setErrorMessage(message) {
            this.errorMessage += (this.errorMessage?"<br/>": "") + message;
        },
        getUserID() {
            return this.userId;
        },
        setUserID(id) {
            this.userId = id;
        },
        getLocale() {
            return this.locale.replace('_', '-');
        },
        setLocale(data) {
            //let self = this;
            if (!data || !data.communication) {
                return false;
            }
            data.communication.forEach(item => {
                if (item.language &&
                    item.language.coding &&
                    item.language.coding.length) {
                    this.locale = item.language.coding[0].code;
                }
            });
            console.log("Locale ", this.locale);
        },
        getSettings() {
            return this.settings;
        },
        setSettings(data) {
            if (data) {
                this.settings = data;
            }
        },
        getUserInfo() {
            return this.userInfo;
        },
        setUserInfo(data) {
            if (data) {
                this.userInfo = data;
            }
        },
        getLRBaseURL() {
            return this.LifeRayBaseURL;
        },
        setLRBaseURL(data) {
            if (data) {
                this.LifeRayBaseURL = data;
            }
        },
        getCurrentView() {
            return this.currentView;
        },
        setCurrentView(viewId) {
            viewId = viewId || "domain";
            this.currentView = viewId;
        },
        isCurrentView(viewId) {
            //return !this.hasError() && !this.isLoading() && this.isMatchView(viewId);
            return !this.isLoading() && this.isMatchView(viewId);
        },
        isMatchView(viewId) {
            return this.currentView === viewId;
        },
        goToView(viewId) {
            Vue.nextTick(
                () => {
                    this.resetError();
                    this.setCurrentView(viewId);
                }
            );
        },
        setNav() {
            //let navElement = document.querySelector(".navigation .content");
            let navElement = document.querySelector(".navigation");
            //let mobileNavElement = document.querySelector(".mobile-navigation .content");
            let mobileNavElement = document.querySelector(".mobile-navigation");
            let mobileQuickLinkElement = document.querySelector(".mobile-quick-links");
            //console.log("nav? ", navElement)
            if (!navElement) {
                if (mobileNavElement) {
                    mobileNavElement.classList.add("hide");
                }
                if (mobileQuickLinkElement) {
                    mobileQuickLinkElement.classList.add("hide");
                }
                return;
            }
            let anchorElements = document.querySelectorAll(".anchor-link");
            //console.log("anchor links? ", anchorElements)
            if (!anchorElements.length) {
                // let navParentElement = document.querySelector(".navigation");
                // let mobileNavElement = document.querySelector(".mobile-navigation");
                // let mobileQuickLinkElement = document.querySelector(".mobile-quick-links");
                if (navElement) navElement.classList.add("hide");
                if (mobileNavElement) mobileNavElement.classList.add("hide");
                if (mobileQuickLinkElement) mobileQuickLinkElement.classList.add("hide");
                return;
            }
            let navContentContainerElement = document.querySelector(".navigation .content");
            if (!navContentContainerElement) {
                let div = document.createElement("div");
                div.classList.add("content");
                navElement.prepend(div);
            }
            let contentHTML = "";
            anchorElements.forEach(el => {
                if (!el.getAttribute("id")) {
                    return true;
                }
                //console.log("Next element? " , el.nextElementSibling.innerText)
                contentHTML += `<a href="#${el.getAttribute("id")}">${
                    el.nextElementSibling &&
                    el.nextElementSibling.innerText? 
                    el.nextElementSibling.innerText : el.getAttribute("id").replace(/_/g, ' ')}</a>`;
            });
            let contentElement = document.createElement("div");
                contentElement.innerHTML = contentHTML;
            let mobileContentElement = contentElement.cloneNode(true);
            navContentContainerElement.appendChild(contentElement);

            let adjustNavPos = () => {
                window.requestAnimationFrame(function() {
                    let topPosition = 48;
                    document.querySelector(".navigation").style.top = topPosition+"px";
                });
            };
            let closeMobileNav = () => {
                document.querySelector(".mobile-navigation").classList.remove("open");
                document.querySelector("body").classList.remove("fixed");
            }

            let navLinkElements = navElement.querySelectorAll("a");
            navLinkElements.forEach(link => {
                link.addEventListener("click", () => {
                    adjustNavPos();
                });
            });

            if (mobileNavElement) {
                let mobileNavContentContainerElement = mobileNavElement.querySelector(".content");
                if (!mobileNavContentContainerElement) {
                    let div = document.createElement("div");
                    div.classList.add("content");
                    mobileNavElement.prepend(div);
                }
                mobileNavContentContainerElement.appendChild(mobileContentElement);
                let mobileNavLinks = mobileNavElement.querySelectorAll("a");
                mobileNavLinks.forEach(item => {
                    item.addEventListener("click", function(e) {
                        e.stopPropagation();
                        closeMobileNav();
                    })
                });
                let mobileCloseButtonElement = mobileNavElement.querySelector(".btn-close");
                if (mobileCloseButtonElement) {
                    mobileCloseButtonElement.addEventListener("click",function(e) {
                        e.stopPropagation();
                        closeMobileNav();
                    });
                }
            }
            window.addEventListener("scroll", function(e) {
                adjustNavPos();
    
            });
            let mobileLinkButton = document.querySelector(".mobile-quick-links button");
            if (mobileLinkButton) {
                mobileLinkButton.addEventListener("click",function(e) {
                    e.stopImmediatePropagation();
                    document.querySelector(".mobile-navigation").classList.add("open");
                    setTimeout(function() {
                        document.querySelector("body").classList.add("fixed");
                    }, 150);
                });
            }
            window.addEventListener("keypress", (e) => {
                if (e.keyCode === 13) {
                    let routerTopic = this.getRouterTopic();
                    if (routerTopic) {
                        window.location.reload();
                        return false;
                    }
                }
                return false;
            });
            window.addEventListener("hashchange", () => {
                let routerTopic = this.getRouterTopic();
                console.log("router Topic when hash? ", routerTopic)
                if (routerTopic === this.activeDomain) return false;
                if (routerTopic) {
                    window.location.reload();
                    return false;
                }
                return false;
            });
            window.addEventListener("resize", function() {
                closeMobileNav();
            });
            let videoNavImage = document.querySelectorAll(".navigation-video-image");
            videoNavImage.forEach(el => {
                el.addEventListener("click", function(e) {
                    closeMobileNav();
                    let videoElement = document.querySelector(".video");
                    if (videoElement) {
                        videoElement.scrollIntoView();
                    }
                });
            });
        },
        setCollapsible() {
            let collapsibleElements = document.querySelectorAll(".collapsible");
            collapsibleElements.forEach(el => {
                el.addEventListener('click', event => {
                    //let collapsibleItems = document.querySelectorAll(".collapsible");
                    let parentEl = event.target.parentElement;
                    let collapsibleItems = parentEl.querySelectorAll(".collapsible");
                    collapsibleItems.forEach(item => {
                        if (item === event.target) return true;
                        item.classList.remove("open");
                    });
                    if (event.target.classList.contains("open")) {
                        event.target.classList.remove("open");
                        return;
                    }
                    event.target.classList.add("open");
                });
            })
        },
        setTileLinkEvent() {
            let tileElements = document.querySelectorAll(".tiles-container .tile");
            tileElements.forEach(el => {
                let anchorLink = el.querySelector("a");
                if (anchorLink && anchorLink.getAttribute("href")) {
                    el.addEventListener("click", function(e) {
                        e.preventDefault();
                        e.stopPropagation();
                        window.open(anchorLink.getAttribute("href"), "_blank");
                        return false;
                    });
                }
            });
        },
        setVideo() {
            let videoElement = document.querySelector(".video");
            if (!videoElement) {
                return;
            }
            let iframeSrc = videoElement.getAttribute("data-iframe-src");
            let videoNavElements = document.querySelectorAll(".navigation-video-image");
            if (!iframeSrc) {
                let videoSection = document.querySelector(".video-section");
                if (videoSection) {
                    videoSection.classList.add("hide");
                }
                videoNavElements.forEach(item => {
                    item.classList.add("hide");
                });
                return;
            }
            let iframeElement = document.createElement("iframe");
            iframeElement.setAttribute("allowfullscreen", true);
            iframeElement.setAttribute("src", videoElement.getAttribute("data-iframe-src"));
            videoElement.appendChild(iframeElement);
            videoElement.classList.add("active");
            videoNavElements.forEach(el => {
                el.addEventListener("click", () => {
                    let ve = document.querySelector(".video iframe");
                    if (ve) {
                        let veSrc = ve.getAttribute("src");
                        if (veSrc.indexOf("?") !== -1) {
                            veSrc = veSrc.substring(0, veSrc.indexOf("?"));
                        }
                        ve.setAttribute("src", veSrc + "?autoPlay=true");
                    }
                });
                el.classList.remove("hide");
            });
        },
        getRouterTopic() {

         //   if (checkIE()) { // detect it's IE11
                var currentPath = window.location.hash.slice(1)
                if (this.$route.path !== currentPath) {
                    this.$router.push(currentPath)
                }
         //   }
            console.log(this.domains)
            console.log("router topic??? ", this.$route.params.topic)

            if (this.$route &&
                this.$route.params && 
                this.$route.params.topic &&
                this.domains.indexOf(this.$route.params.topic.toLowerCase()) !== -1) {
                return this.$route.params.topic;
            }
            let arrHashText = String(location.hash).split("#");
            if (arrHashText && arrHashText[1]) {
                let matchText = arrHashText[1].replace("/", "");
                if (this.domains.indexOf(matchText.toLowerCase()) !== -1) {
                    return matchText;
                }
                return "";
            } 
            return "";
        },
        setSelectedDomain() {
            let routerTopic = this.getRouterTopic();
            console.log("Router topic? ", routerTopic)
            if (routerTopic) {
                this.activeDomain = routerTopic;
                return;
            }
            this.activeDomain = getUrlParameter("topic") || "mood_changes";
        },
        getSelectedDomain() {
            //return this.activeDomain;
            //return "substudy";
            //return "hot_flashes"
            //example URL that works: https://amy-dev.cirg.washington.edu/substudy-tailored-content#/insomnia
            return this.activeDomain;
         },
         getSearchURL() {
             //TODO use current domain name as tag
             //pass in locale info
             return `/api/asset/tag/${this.getSelectedDomain()}?locale_code=${this.getLocale()}`;
             //CORS issue with querying LR directly, TODO: uncomment this when resolves
            //  return  `${this.getLRBaseURL()}/c/portal/truenth/asset/query?content=true&anyTags=${this.getSelectedDomain()}&languageId=${this.getLocale()}`;
         },
        onDomainContentDidLoad() {
            console.log("WTF?")
            setTimeout(function() {
                this.setInitView();
                this.setCurrentView("domain");
            }.bind(this), 150);
            this.setNav();
            this.setCollapsible();
            this.setVideo();
            this.setTileLinkEvent();
        },
        getDomainContent() {
            if (this.domainContent) {
                //already populated
                this.setInitView();
                return this.domainContent;
            }
            this.$http(this.getSearchURL()).then(
                response => {
                //LR URL returns this
                //console.log("response? ", JSON.parse(response));
                // let content = JSON.parse(response);
                // this.setDomainContent(content["results"][0]["content"]);
                //console.log("response? ", response);
                if (response) {
                    this.setDomainContent(response);
                    Vue.nextTick()
                    .then(() => {
                        // DOM updated
                        this.onDomainContentDidLoad();
                    });
                    
                } else {
                    this.setErrorMessage(`Error occurred retrieving content: no content returned.`);
                    this.setInitView(true);
                }
            }).catch(e => {
                console.log("failed? ", e)
                this.getContentAttempt++;
                if (this.getContentAttempt <= 2) {
                    this.getDomainContent();
                    return;
                } else {
                    this.getContentAttempt = 0;
                }
                console.log(e)
                this.setErrorMessage(`Error occurred retrieving content: ${e.statusText}`);
                this.loading = false;
               // this.setInitView();
            });
        },
        setDomainContent: function(data) {
            let content = tryParseJSON(data);
            console.log(content)
            if (content) {
                this.domainContent = content["results"][0]["content"];
                return;
            }
            this.domainContent = data;
        },
        goHome: function() {
            this.goToView("domain");
        }
    }
};
