document.addEventListener("DOMContentLoaded", () => {
    const uploadForm = document.getElementById("upload-form");
    const generateBtn = document.getElementById("generate-btn");
    const btnText = generateBtn.querySelector("span");
    const spinner = generateBtn.querySelector(".spinner");
    const publishStatus = document.getElementById("publish-status");
    
    const stepInput = document.getElementById("step-input");
    const stepSuccess = document.getElementById("step-success");
    const youtubeLink = document.getElementById("youtube-link");
    
    // Live feedback elements
    const liveFeedback = document.getElementById("live-feedback");
    const logBox = document.getElementById("log-box");
    const metadataPreview = document.getElementById("metadata-preview");
    const thumbnailPreview = document.getElementById("thumbnail-preview");
    const genTitle = document.getElementById("gen-title");
    const genDesc = document.getElementById("gen-desc");
    const genTags = document.getElementById("gen-tags");
    const genThumbnail = document.getElementById("gen-thumbnail");

    uploadForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        
        const videoFile = document.getElementById("video-file").files[0];
        const promptText = document.getElementById("prompt").value.trim();

        if (!videoFile || !promptText) return;

        // UI State -> Loading
        btnText.classList.add("hidden");
        spinner.classList.remove("hidden");
        generateBtn.disabled = true;
        publishStatus.classList.remove("hidden");
        
        liveFeedback.classList.remove("hidden");
        logBox.innerHTML = "";
        
        const formData = new FormData();
        formData.append("video", videoFile);
        formData.append("prompt", promptText);

        // Generate AI Thumbnail using Puter.js (Nano Banana / Gemini)
        logBox.innerHTML = "<div>Generating AI Thumbnail (Nano Banana via Puter)...</div>";
        try {
            // Race between generation and a 60s timeout
            const imageElement = await Promise.race([
                puter.ai.txt2img(
                    "Create a 1280x720 landscape YouTube thumbnail, 16:9 aspect ratio, edge to edge with no borders, no blur, no letterboxing. Highly engaging clickbait style, no text overlay, topic: " + promptText + ". Cinematic, 4k, vibrant colors, high contrast, eye-catching.",
                    { model: "google/gemini-3-pro-image-preview" }
                ),
                new Promise((_, reject) => setTimeout(() => reject(new Error("Timeout")), 60000))
            ]);
            
            const thumbResponse = await fetch(imageElement.src);
            const thumbBlob = await thumbResponse.blob();
            formData.append("thumbnail", thumbBlob, "thumbnail.png");
            
            logBox.innerHTML += "<div>✅ Nano Banana Thumbnail Generated Successfully!</div>";
            
            // Show it immediately in the preview
            thumbnailPreview.classList.remove("hidden");
            genThumbnail.src = URL.createObjectURL(thumbBlob);
        } catch (e) {
            console.error("Puter Image Gen failed:", e);
            logBox.innerHTML += "<div>⚠️ Puter thumbnail gen failed (" + e.message + "). Server will extract a frame instead.</div>";
        }

        try {
            const response = await fetch("/api/publish", {
                method: "POST",
                body: formData
            });
            
            const reader = response.body.getReader();
            const decoder = new TextDecoder("utf-8");
            let buffer = "";
            
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                buffer += decoder.decode(value, { stream: true });
                const parts = buffer.split("\n\n");
                buffer = parts.pop(); // keep the last incomplete chunk
                
                for (const part of parts) {
                    if (part.startsWith("data: ")) {
                        const dataStr = part.substring("data: ".length);
                        try {
                            const item = JSON.parse(dataStr);
                            
                            if (item.type === "log") {
                                logBox.innerHTML += `<div>${item.message}</div>`;
                                logBox.scrollTop = logBox.scrollHeight;
                            } else if (item.type === "metadata") {
                                metadataPreview.classList.remove("hidden");
                                genTitle.textContent = item.metadata.title;
                                genDesc.textContent = item.metadata.description;
                                genTags.textContent = (item.metadata.tags || []).join(", ");
                            } else if (item.type === "thumbnail") {
                                thumbnailPreview.classList.remove("hidden");
                                if (item.path) {
                                    // add a cache-buster query param so it forces a reload if the name is the same
                                    genThumbnail.src = item.path + "?t=" + new Date().getTime();
                                }
                            } else if (item.type === "complete") {
                                stepInput.classList.remove("active-step");
                                stepInput.classList.add("hidden");
                                
                                stepSuccess.classList.remove("hidden");
                                stepSuccess.classList.add("active-step");
                                
                                if (item.youtube_url) {
                                    youtubeLink.href = item.youtube_url;
                                } else {
                                    youtubeLink.classList.add("hidden");
                                }
                            } else if (item.type === "error") {
                                alert("Error publishing: " + (item.message || "Unknown error"));
                            }
                        } catch (e) {
                            console.error("Error parsing SSE JSON", e);
                        }
                    }
                }
            }
            
        } catch (err) {
            console.error(err);
            alert("Network error occurred during upload.");
        } finally {
            // UI State -> Normal
            btnText.classList.remove("hidden");
            spinner.classList.add("hidden");
            generateBtn.disabled = false;
            publishStatus.classList.add("hidden");
        }
    });
});
