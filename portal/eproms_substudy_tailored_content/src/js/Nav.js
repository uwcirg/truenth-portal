import {isInViewport} from "./Utility";
/*
 * methods for side navigation panel element 
 * the element content is dynamically populated based on anchor links available in content
 */
export default {
    methods: {
        getNavElement() {
            return document.querySelector(".navigation");
        },
        getMobileNavElement() {
            return document.querySelector(".mobile-navigation");
        },
        getMobileQuickLinkElement() {
            return document.querySelector(".mobile-quick-links");
        },
        getAnchorLinkElements() {
            return document.querySelectorAll(".anchor-link");
        },
        initNav() {
            this.setNavContent();
            setTimeout(() => {
                this.initAllNavEvents();
            }, 0);
        },
        onNoNav() {
            let navElement = this.getNavElement();
            let mobileNavElement = this.getMobileNavElement();
            let mobileQuickLinkElement = this.getMobileQuickLinkElement();
            if (navElement) {
                navElement.classList.add("hide");
            }
            if (mobileNavElement) {
                mobileNavElement.classList.add("hide");
            }
            if (mobileQuickLinkElement) {
                mobileQuickLinkElement.classList.add("hide");
            }
        },
        setNavContent() {
            let navElement = this.getNavElement();
            if (!navElement) {
                this.onNoNav();
                return;
            }
            let anchorLinkElements = this.getAnchorLinkElements();
            if (!anchorLinkElements) {
                this.onNoNav();
                return;
            }

            let navContentContainerElement = navElement.querySelector(".content");
            if (!navContentContainerElement) {
                let div = document.createElement("div");
                div.classList.add("content");
                navElement.prepend(div);
            }
            let contentHTML = "";
            anchorLinkElements.forEach(el => {
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
            navContentContainerElement.appendChild(contentElement);
            let mobileNavElement = this. getMobileNavElement();
            if (mobileNavElement) {
                let mobileContentElement = contentElement.cloneNode(true);
                let mobileNavContentContainerElement = mobileNavElement.querySelector(".content");
                if (!mobileNavContentContainerElement) {
                    let div = document.createElement("div");
                    div.classList.add("content");
                    mobileNavElement.prepend(div);
                }
                mobileNavContentContainerElement.appendChild(mobileContentElement);
            }
            this.setVideoNavVis();
        },
        adjustNavPos() {
            let navElement = this.getNavElement();
            if (!navElement) return;
            window.requestAnimationFrame(function() {
                let topPosition = 48;
                let portalWrapperElement = document.querySelector("#tnthNavWrapper");
                if (isInViewport(portalWrapperElement)) {
                    topPosition = portalWrapperElement.offsetHeight + topPosition;
                }
                navElement.style.top = topPosition+"px";
            });
        },
        openMobileNav() {
            let mobileNavElement = this.getMobileNavElement();
            if (!mobileNavElement) return;
            mobileNavElement.classList.add("open");
            setTimeout(function() {
                document.querySelector("body").classList.add("fixed");
            }, 150);
        },
        closeMobileNav() {
            let mobileNavElement = this.getMobileNavElement();
            if (!mobileNavElement) return;
            mobileNavElement.classList.remove("open");
            document.querySelector("body").classList.remove("fixed");
        },
        initAllNavEvents() {
            this.initNavElementEvents();
            this.initWindowNavEvents();
            this.initVideoNavEvent();
        },
        getVideoNavElements() {
            return document.querySelectorAll(".navigation-video-image");
        },
        setVideoNavVis() {

            let videoElement = document.querySelector(".video");
            console.log("WTF?? ", videoElement.getAttribute("data-iframe-src"))
            if (!videoElement || (!videoElement.getAttribute("data-iframe-src"))) {
                let videoNavImages = this.getVideoNavElements();
                console.log('nav? ', videoNavImages)
                videoNavImages.forEach(el => {
                    el.style.display = "none";
                });
            }
        },
        initVideoNavEvent() {
            let videoNavImages = this.getVideoNavElements();
            videoNavImages.forEach(el => {
                el.addEventListener("click", () => {
                    this.closeMobileNav();
                    let videoElement = document.querySelector(".video");
                    if (videoElement) {
                        videoElement.scrollIntoView();
                    }
                });
            });
        },
        initWindowNavEvents() {
            window.addEventListener("scroll", e => {
                e.stopPropagation();
                this.adjustNavPos();
            });
            window.addEventListener("resize", () => {
                this.closeMobileNav();
            });
        },
        initNavElementEvents() {
            let navElement = this.getNavElement();
            if (navElement) {
                let navLinkElements = navElement.querySelectorAll("a");
                navLinkElements.forEach(link => {
                    link.addEventListener("click", () => {
                        this.adjustNavPos();
                    });
                });
            }
            let mobileNavElement = this. getMobileNavElement();
            if (!mobileNavElement) {
                return;
            }
            let mobileNavLinks = mobileNavElement.querySelectorAll("a");
            mobileNavLinks.forEach(item => {
                item.addEventListener("click",  e => {
                    e.stopPropagation();
                    this.closeMobileNav();
                })
            });
            let mobileCloseButtonElement = mobileNavElement.querySelector(".btn-close");
            if (mobileCloseButtonElement) {
                mobileCloseButtonElement.addEventListener("click", e => {
                    e.stopPropagation();
                    this.closeMobileNav();
                });
            }
            let mobileQuickLinkElement = this.getMobileQuickLinkElement();
            let mobileQuickLinkButton = mobileQuickLinkElement.querySelector("button");
            if (mobileQuickLinkButton) {
                mobileQuickLinkButton.addEventListener("click", e => {
                    e.stopImmediatePropagation();
                    setTimeout(() => {
                        this.openMobileNav();
                    }, 150);
                });
            }
        } //end initNavElementEvents
    }
}
