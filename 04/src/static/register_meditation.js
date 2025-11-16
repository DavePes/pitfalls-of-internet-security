document.addEventListener("DOMContentLoaded", function () {
  const start = document.querySelector("#startButton");
  const stop = document.querySelector("#stopButton");
  start.onclick = startMeditation;
  stop.onclick = stopMeditation;
});
