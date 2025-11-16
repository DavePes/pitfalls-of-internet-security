// Meditation Color Wave Visualization
// This script creates a relaxing color wave animation on canvas

let animationId = null;
let canvas = null;
let ctx = null;
let waveSpeed = 0.5;
let offset = 0;

/**
 * Initialize the meditation visualization
 */
function initMeditation() {
  canvas = document.getElementById("meditationCanvas");
  if (!canvas) {
    console.error("Canvas element not found");
    return false;
  }

  ctx = canvas.getContext("2d");
  return true;
}

/**
 * Start the meditation visualization
 */
function startMeditation() {
  if (!canvas && !initMeditation()) {
    return;
  }

  // Stop any existing animation
  if (animationId) {
    stopMeditation();
  }

  // Get the expression from input field
  const exprInput = document.getElementById("visualExpr");
  if (exprInput && exprInput.value) {
    try {
      const result = eval(exprInput.value);

      // Only update waveSpeed if result is a valid number
      if (typeof result === "number" && !isNaN(result)) {
        waveSpeed = Math.abs(result);
        // Clamp between reasonable values
        waveSpeed = Math.min(Math.max(waveSpeed, 0.01), 2);
      }
    } catch (e) {
      console.error("Invalid expression:", e);
      // Continue with default speed on error
    }
  }

  // Start the animation loop
  animate();
}

/**
 * Stop the meditation visualization
 */
function stopMeditation() {
  if (animationId) {
    cancelAnimationFrame(animationId);
    animationId = null;
  }
}

/**
 * Animation loop - draws the color waves
 */
function animate() {
  if (!ctx || !canvas) return;

  // Clear canvas
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  // Update offset for wave animation
  offset += waveSpeed * 2;

  // Draw multiple color waves
  const numWaves = 5;
  const waveHeight = canvas.height / numWaves;

  for (let i = 0; i < numWaves; i++) {
    drawWave(i, waveHeight, offset);
  }

  // Continue animation
  animationId = requestAnimationFrame(animate);
}

/**
 * Draw a single color wave
 */
function drawWave(index, height, timeOffset) {
  const width = canvas.width;
  const yOffset = index * height;
  const hue = (index * 60 + timeOffset) % 360;

  ctx.beginPath();
  ctx.moveTo(0, yOffset);

  // Create wave path
  for (let x = 0; x <= width; x++) {
    const y =
      yOffset + Math.sin((x + timeOffset) * 0.01 + index) * 30 + height / 2;
    ctx.lineTo(x, y);
  }

  ctx.lineTo(width, canvas.height);
  ctx.lineTo(0, canvas.height);
  ctx.closePath();

  // Fill with gradient
  const gradient = ctx.createLinearGradient(0, yOffset, 0, yOffset + height);
  gradient.addColorStop(0, `hsla(${hue}, 70%, 60%, 0.8)`);
  gradient.addColorStop(1, `hsla(${hue + 30}, 70%, 50%, 0.6)`);

  ctx.fillStyle = gradient;
  ctx.fill();
}

/**
 * Auto-initialize when page loads
 */
window.addEventListener("load", function () {
  if (document.getElementById("meditationCanvas")) {
    initMeditation();
  }
});

// Cleanup on page unload
window.addEventListener("beforeunload", function () {
  stopMeditation();
});
