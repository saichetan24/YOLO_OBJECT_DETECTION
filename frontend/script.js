const video = document.getElementById("camera");
const resultDiv = document.getElementById("result");
const captureBtn = document.getElementById("capture");

async function startCamera() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 1280, height: 720 } });
        video.srcObject = stream;
        await video.play();
    } catch (err) {
        console.error("Could not start camera", err);
        resultDiv.innerText = "Error accessing camera: " + err.message;
    }
}

startCamera();

captureBtn.addEventListener("click", async () => {
    captureBtn.disabled = true;
    captureBtn.textContent = "Detecting...";
    resultDiv.innerHTML = "";

    try {
        const canvas = document.createElement("canvas");
        canvas.width = video.videoWidth || 640;
        canvas.height = video.videoHeight || 480;
        const ctx = canvas.getContext("2d");
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

        const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.8));
        if (!blob) throw new Error("Failed to create image blob");

        const formData = new FormData();
        formData.append("frame", blob, "frame.jpg");

        const res = await fetch("http://localhost:5000/detect", {
            method: "POST",
            mode: "cors",
            body: formData
        });

        if (!res.ok) {
            const txt = await res.text();
            throw new Error(`Server error ${res.status}: ${txt}`);
        }

        const data = await res.json();
        console.log(data);
            // data.detected is now a mapping name->count
            if (data.detected && Object.keys(data.detected).length > 0) {
                const entries = Object.entries(data.detected).map(([name, cnt]) => {
                    return cnt > 1 ? `${name} (${cnt})` : name;
                });
                resultDiv.innerHTML = `<h2>Detected: ${entries.join(", ")}</h2>`;
                if (data.annotated) {
                    const img = document.createElement("img");
                    img.src = data.annotated;
                    img.style.maxWidth = "70%";
                    img.style.display = "block";
                    img.style.margin = "12px auto";
                    resultDiv.appendChild(img);
                }
            } else {
                resultDiv.innerHTML = `<h2>No Objects Detected</h2>`;
            }
    } catch (err) {
        console.error(err);
        resultDiv.innerHTML = `<h2>Error: ${err.message}</h2>`;
    } finally {
        captureBtn.disabled = false;
        captureBtn.textContent = "Capture & Detect";
    }
});
