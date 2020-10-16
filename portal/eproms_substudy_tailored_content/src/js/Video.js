import {isInViewport} from "./Utility";
export default {
    methods: {
        getIframeAttribute() {
            let videoElement = this.getVideoElement();
            if (videoElement) return videoElement.getAttribute("data-iframe-src");
            return "";
        },
        getVideoElement() {
            return document.querySelector(".video");
        },
        setVideoIframe() {
            let videoElement = this.getVideoElement();
            if (!videoElement) {
                return;
            }
            let videoSrc = this.getIframeAttribute();
            if (!videoSrc) {
                return;
            }
            if (videoElement.classList.contains("active")) {
                return;
            }
            let iframeElement = document.createElement("iframe");
            iframeElement.setAttribute("allowfullscreen", true);
            iframeElement.setAttribute("src", videoSrc);
            videoElement.appendChild(iframeElement);
            videoElement.classList.add("active");
        },
        hideVideo() {
            let videoSection = document.querySelector(".video-section");
            if (videoSection) {
                videoSection.style.display = "none";
            }
        },
        initVideo() {
            let videoElement = this.getVideoElement();
            if (!videoElement) {
                this.hideVideo();
                return;
            }
            if (!this.getIframeAttribute()) {
                this.hideVideo();
                return;
            }

            if (videoElement.getAttribute("data-preload")) {
                this.setVideoIframe();
            }

            window.addEventListener("scroll", e => {
                e.stopPropagation();
                window.requestAnimationFrame(() => {
                    if (!isInViewport(videoElement)) {
                        return false;
                    }
                    this.setVideoIframe();
                });
                
            });
            let videoNavElements = document.querySelectorAll(".navigation-video-image");
            videoNavElements.forEach(el => {
                el.addEventListener("click", () => {
                    this.setVideoIframe();
                    let ve = videoElement.querySelector("iframe");
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
        }
    }
}
