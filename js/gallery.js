(function () {
  const dialog = document.querySelector("dialog.lightbox");
  if (!dialog) return;
  const img = dialog.querySelector("img");
  const caption = dialog.querySelector(".lightbox-caption");
  const prev = dialog.querySelector("[data-prev]");
  const next = dialog.querySelector("[data-next]");
  let items = [];
  let index = 0;

  function read(button) {
    const figure = button.closest("figure");
    const title = figure.querySelector("h2, .shot span");
    const copy = figure.querySelector("p");
    return {
      src: button.querySelector("img").currentSrc || button.querySelector("img").src,
      full: button.dataset.full || button.querySelector("img").src,
      title: title ? title.textContent.trim() : button.querySelector("img").alt,
      text: copy ? copy.textContent.trim() : ""
    };
  }

  function show(i) {
    index = (i + items.length) % items.length;
    const item = items[index];
    img.src = item.full;
    img.alt = item.title || "";
    caption.innerHTML = "";
    if (item.title) {
      const strong = document.createElement("strong");
      strong.textContent = item.title;
      caption.appendChild(strong);
    }
    if (item.text) {
      if (item.title) caption.appendChild(document.createElement("br"));
      caption.appendChild(document.createTextNode(item.text));
    }
    prev.hidden = next.hidden = items.length < 2;
  }

  document.querySelectorAll("[data-gallery]").forEach(function (group) {
    const buttons = [...group.querySelectorAll("button")];
    buttons.forEach(function (button, i) {
      button.addEventListener("click", function () {
        items = buttons.map(read);
        show(i);
        dialog.showModal();
      });
    });
  });

  prev.addEventListener("click", function () { show(index - 1); });
  next.addEventListener("click", function () { show(index + 1); });
  dialog.querySelector("[data-close]").addEventListener("click", function () {
    dialog.close();
  });
  dialog.addEventListener("click", function (event) {
    if (event.target === dialog) dialog.close();
  });
  dialog.addEventListener("close", function () { img.removeAttribute("src"); });
  dialog.addEventListener("keydown", function (event) {
    if (event.key === "ArrowLeft") show(index - 1);
    if (event.key === "ArrowRight") show(index + 1);
  });
})();
