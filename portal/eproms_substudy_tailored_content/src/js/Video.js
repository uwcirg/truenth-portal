import {isInViewport} from "./Utility";
export default {
    methods: {
        getIframeAttribute(videoElement) {
            videoElement = videoElement || this.getVideoElement();
            if (videoElement) return videoElement.getAttribute("data-iframe-src");
            return "";
        },
        getVideoElement() {
            return document.querySelector(".video");
        },
        setVideoIframe(videoElement) {
            videoElement = videoElement || this.getVideoElement();
            if (!videoElement) {
                return;
            }
            let videoSrc = this.getIframeAttribute(videoElement);
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
        hideVideo(videoElement) {
            videoElement = videoElement || this.getVideoElement();
            let videoSection = document.querySelector(".video-section");
            if (videoSection) {
                videoSection.style.display = "none";
            }
            if (videoElement) {
                videoElement.style.display = "none";
            }
        },
        initVideoEvents() {
            window.addEventListener("scroll", e => {
                e.stopPropagation();
                window.requestAnimationFrame(() => {
                    let videoElements = document.querySelectorAll(".video");
                    videoElements.forEach(el => {
                        if (!isInViewport(el.parentNode || el)) {
                            return false;
                        }
                        this.setVideoIframe(el);
                    });
                });
            });
            let videoNavElements = document.querySelectorAll(".navigation-video-image");
            videoNavElements.forEach(el => {
                el.addEventListener("click", () => {
                    this.setVideoIframe(videoElement);
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
        },
        initVideo(videoElement) {
            videoElement = videoElement || this.getVideoElement();
            if (!videoElement) {
                this.hideVideo(videoElement);
                return;
            }
            if (!this.getIframeAttribute(videoElement)) {
                this.hideVideo(videoElement);
                return;
            }

            if (videoElement.getAttribute("data-preload")) {
                this.setVideoIframe(videoElement);
            }
        }
    }
}
