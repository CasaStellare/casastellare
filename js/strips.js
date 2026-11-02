(function () {
  const row = document.querySelector(".strip-row");
  if (!row) return;
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  function shuffle(list) {
    const copy = list.slice();
    for (let i = copy.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      const swap = copy[i];
      copy[i] = copy[j];
      copy[j] = swap;
    }
    return copy;
  }

  row.querySelectorAll(".panel").forEach(function (panel) {
    const frames = [...panel.querySelectorAll("img")];
    if (frames.length < 2) return;

    let order = shuffle(frames);
    let step = 0;
    order[0].classList.add("is-on");
    panel.classList.add("is-live");

    function advance() {
      const previous = order[step];
      step += 1;
      if (step >= order.length) {
        order = shuffle(frames);
        if (order[0] === previous) order.push(order.shift());
        step = 0;
      }
      previous.classList.remove("is-on");
      order[step].classList.add("is-on");
      window.setTimeout(advance, 3800 + Math.random() * 5200);
    }

    window.setTimeout(advance, 2200 + Math.random() * 5400);
  });
})();
