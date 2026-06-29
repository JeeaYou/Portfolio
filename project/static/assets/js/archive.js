// static/assets/js/archive.js

document.addEventListener("DOMContentLoaded", function () {
  const CARDS_PER_PAGE = 9;

  const filterButtons = document.querySelectorAll(".archive-filter-btn");
  const archiveGrid = document.getElementById("archiveGrid");
  const archiveCards = Array.from(document.querySelectorAll(".archive-card"));
  const archiveEmpty = document.getElementById("archiveEmpty");
  const sortSelect = document.getElementById("archiveSort");
  const pagination = document.getElementById("archivePagination");

  let currentFilter = "all";
  let currentSort = "latest";
  let currentPage = 1;

  function parseDate(value) {
    if (!value) {
      return new Date(0);
    }

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
      return new Date(0);
    }

    return date;
  }

  function getFilteredCards() {
    return archiveCards.filter(function (card) {
      const cardCategory = card.dataset.category;

      if (currentFilter === "all") {
        return true;
      }

      return cardCategory === currentFilter;
    });
  }

  function getSortedCards(cards) {
    return [...cards].sort(function (a, b) {
      const dateA = parseDate(a.dataset.date);
      const dateB = parseDate(b.dataset.date);

      if (currentSort === "oldest") {
        return dateA - dateB;
      }

      return dateB - dateA;
    });
  }

  function hideAllCards() {
    archiveCards.forEach(function (card) {
      card.style.display = "none";
    });
  }

  function updateEmptyState(totalCount) {
    if (!archiveEmpty) {
      return;
    }

    if (totalCount === 0) {
      archiveEmpty.classList.add("is-show");
    } else {
      archiveEmpty.classList.remove("is-show");
    }
  }

  function createPageButton(text, page, options) {
    const button = document.createElement("button");

    button.type = "button";
    button.className = "page-btn";
    button.textContent = text;

    if (options && options.active) {
      button.classList.add("is-active");
    }

    if (options && options.disabled) {
      button.disabled = true;
      button.classList.add("is-disabled");
    }

    if (!button.disabled) {
      button.addEventListener("click", function () {
        currentPage = page;
        renderArchive(true);
      });
    }

    return button;
  }

  function createDots() {
    const dots = document.createElement("span");
    dots.className = "page-dots";
    dots.textContent = "...";
    return dots;
  }

  function renderPagination(totalPages) {
    if (!pagination) {
      return;
    }

    pagination.innerHTML = "";

    if (totalPages <= 1) {
      pagination.style.display = "none";
      return;
    }

    pagination.style.display = "flex";

    pagination.appendChild(
      createPageButton("‹", currentPage - 1, {
        disabled: currentPage === 1,
      })
    );

    const maxVisiblePages = 5;
    let startPage = Math.max(1, currentPage - 2);
    let endPage = Math.min(totalPages, currentPage + 2);

    if (currentPage <= 3) {
      endPage = Math.min(totalPages, maxVisiblePages);
    }

    if (currentPage >= totalPages - 2) {
      startPage = Math.max(1, totalPages - maxVisiblePages + 1);
    }

    if (startPage > 1) {
      pagination.appendChild(createPageButton("1", 1));

      if (startPage > 2) {
        pagination.appendChild(createDots());
      }
    }

    for (let page = startPage; page <= endPage; page += 1) {
      pagination.appendChild(
        createPageButton(String(page), page, {
          active: page === currentPage,
        })
      );
    }

    if (endPage < totalPages) {
      if (endPage < totalPages - 1) {
        pagination.appendChild(createDots());
      }

      pagination.appendChild(createPageButton(String(totalPages), totalPages));
    }

    pagination.appendChild(
      createPageButton("›", currentPage + 1, {
        disabled: currentPage === totalPages,
      })
    );
  }

  function renderArchive(shouldScroll) {
    const filteredCards = getFilteredCards();
    const sortedCards = getSortedCards(filteredCards);
    const totalCount = sortedCards.length;
    const totalPages = Math.ceil(totalCount / CARDS_PER_PAGE);

    hideAllCards();
    updateEmptyState(totalCount);

    if (totalCount === 0) {
      renderPagination(0);
      return;
    }

    if (currentPage > totalPages) {
      currentPage = totalPages;
    }

    if (currentPage < 1) {
      currentPage = 1;
    }

    const startIndex = (currentPage - 1) * CARDS_PER_PAGE;
    const endIndex = startIndex + CARDS_PER_PAGE;
    const visibleCards = sortedCards.slice(startIndex, endIndex);

    sortedCards.forEach(function (card) {
      archiveGrid.appendChild(card);
    });

    visibleCards.forEach(function (card) {
      card.style.display = "";
    });

    renderPagination(totalPages);

    if (shouldScroll) {
      const archiveSection = document.querySelector(".archive-section");

      if (archiveSection) {
        archiveSection.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
      }
    }
  }

  filterButtons.forEach(function (button) {
    button.addEventListener("click", function () {
      currentFilter = button.dataset.filter || "all";
      currentPage = 1;

      filterButtons.forEach(function (btn) {
        btn.classList.remove("is-active");
      });

      button.classList.add("is-active");

      renderArchive(false);
    });
  });

  if (sortSelect) {
    sortSelect.addEventListener("change", function () {
      currentSort = sortSelect.value;
      currentPage = 1;
      renderArchive(false);
    });
  }

  renderArchive(false);
});