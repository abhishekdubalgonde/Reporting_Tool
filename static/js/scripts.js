// =============================
// Profile Settings Management
// =============================

const profilePic = document.getElementById('profile-pic');
const profileInput = document.getElementById('profile-pic-input');
const bgInput = document.getElementById('bg-image-input');
const themeSelect = document.getElementById('theme-select');
const resetBtn = document.getElementById('reset-btn');

const themes = {
  default: { '--main-color': '#000', '--text-color': '#f5f5f5', '--bg-color': '#ADD8E6' },
  dark: { '--main-color': '#111', '--text-color': '#fff', '--bg-color': '#222' },
  blue: { '--main-color': '#001F3F', '--text-color': '#f5f5f5', '--bg-color': '#0074D9' },
  neon: { '--main-color': '#0f0f0f', '--text-color': '#39FF14', '--bg-color': '#121212' }
};

// =============================
// Restore Settings from Flask
// =============================
window.addEventListener('load', async () => {
  try {
    const res = await fetch('/get_settings');
    const data = await res.json();

    // Apply saved profile picture
    if (data.profilePic) profilePic.src = data.profilePic;

    // Apply saved background image
    if (data.backgroundImg)
      document.body.style.backgroundImage = `url(${data.backgroundImg})`;

    // Apply saved theme
    if (data.theme && themes[data.theme]) {
      themeSelect.value = data.theme;
      const theme = themes[data.theme];
      for (let key in theme)
        document.documentElement.style.setProperty(key, theme[key]);
    } else {
      applyTheme('default');
    }
  } catch (err) {
    console.error('Error loading settings:', err);
  }
});

// =============================
// Save Settings to Flask
// =============================
async function saveSettings() {
  const settings = {
    profilePic: profilePic.src,
    backgroundImg: document.body.style.backgroundImage
      .replace('url("', '')
      .replace('")', '')
      .trim(),
    theme: themeSelect.value
  };

  try {
    await fetch('/save_settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings)
    });
  } catch (err) {
    console.error('Error saving settings:', err);
  }
}

// =============================
// Theme Handling
// =============================
function applyTheme(themeName) {
  const theme = themes[themeName];
  if (theme) {
    for (let key in theme)
      document.documentElement.style.setProperty(key, theme[key]);
  }
}

// =============================
// Event Listeners
// =============================

// Profile Picture Upload
profileInput.addEventListener('change', async e => {
  const file = e.target.files[0];
  if (file) {
    const url = URL.createObjectURL(file);
    profilePic.src = url;
    await saveSettings();
  }
});

// Background Image Upload
bgInput.addEventListener('change', async e => {
  const file = e.target.files[0];
  if (file) {
    const url = URL.createObjectURL(file);
    document.body.style.backgroundImage = `url(${url})`;
    await saveSettings();
  }
});

// Theme Change
themeSelect.addEventListener('change', async () => {
  const selected = themeSelect.value;
  applyTheme(selected);
  await saveSettings();
});

// Reset to Default
resetBtn?.addEventListener('click', async () => {
  profilePic.src = '/static/default_profile.png';
  document.body.style.backgroundImage = "url('/static/default_bg.jpg')";
  themeSelect.value = 'default';
  applyTheme('default');
  await saveSettings();
});

// =============================
// Sidebar Menu Toggle
// =============================
const btn = document.getElementById('menu-btn');
const menu = document.getElementById('side-menu');

btn?.addEventListener('click', () => {
  menu.classList.toggle('menu-open');

  // Change icon < >
  btn.textContent = menu.classList.contains('menu-open') ? '>' : '<';

  // Rotate button
  btn.classList.toggle('rotate');
});
