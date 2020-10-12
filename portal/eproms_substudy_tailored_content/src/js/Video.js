import {isInViewport} from "./Utility";
export default {
    methods: {
        getVideoElement() {
            return document.querySelector(".video");
        },
        setVideoIframe() {
            let videoElement = this.getVideoElement();
            if (!videoElement) {
                return;
            }
            if (videoElement.classList.contains("active")) {
                return;
            }
            let iframeElement = document.createElement("iframe");
            iframeElement.setAttribute("allowfullscreen", true);
            iframeElement.setAttribute("src", videoElement.getAttribute("data-iframe-src"));
            videoElement.appendChild(iframeElement);
            videoElement.classList.add("active");
        },
        initVideo() {
            let videoElement = this.getVideoElement();
            if (!videoElement) {
                return;
            }
            let videoNavElements = document.querySelectorAll(".navigation-video-image");
            window.addEventListener("scroll", e => {
                e.stopPropagation();
                window.requestAnimationFrame(() => {
                    if (!isInViewport(videoElement)) {
                        return false;
                    }
                    this.setVideoIframe();
                });
                
            });
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
