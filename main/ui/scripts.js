// 全局状态
let fontList = [];
let selectedSteps = new Set();
let pngOptions = {
  bgMode: 'dynamic',
  gradientCycle: 100,
  gradientType: 'smooth',
  gradientColors: '',
  animateElements: [],
  animationType: 'smooth',
  animationAmplitude: 50,
  movementSpeed: 0.1,
  animationSpeed: 1.0,
  showEncoding: false,
  showBlockPosition: false,
  showGlobalPosition: false,
  showBlockProgressBar: false,
  showGlobalProgressBar: false,
  showNamesInfo: false,
  showSideSpinner: false,
  disableCombOverlay: false,
  spinnerStrings: '-,/,|,\\',
  spinnerStepInterval: 1,
  contentPositionType: 'center',
  contentOffsetX: 0,
  contentOffsetY: 0,
  scaleFactor: 1.0,
  shuffleContent: false,
  workers: 8,
  pngQuality: 'balanced',
  forceRegenerate: false,
  flashColor: ''
};

// 初始化
document.addEventListener('DOMContentLoaded', function() {
  initSections();
  initNav();
  initEventListeners();
  updateUI();
  generateCommands();
});

function initSections() {
  document.querySelectorAll('.section').forEach(section => {
    section.classList.add('collapsible');
    const title = section.querySelector('.section-title');
    title.addEventListener('click', function(e) {
      if (!e.target.closest('button') && !e.target.closest('input') && !e.target.closest('select')) {
        section.classList.toggle('collapsed');
      }
    });
  });
}

function initNav() {
  document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', function() {
      const sectionNum = this.dataset.nav;
      document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
      this.classList.add('active');
      
      const section = document.querySelector(`[data-section="${sectionNum}"]`);
      if (section) {
        section.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });
}

function initEventListeners() {
  // 背景模式变化
  document.querySelectorAll('[data-png-option="bg-mode"]').forEach(card => {
    card.addEventListener('click', function() {
      const mode = this.dataset.value;
      document.getElementById('rainbowConfig').style.display = mode === 'rainbow' ? 'block' : 'none';
    });
  });

  // 转圈动画显示
  document.getElementById('showSideSpinner').addEventListener('change', function() {
    document.getElementById('spinnerConfig').style.display = this.checked ? 'block' : 'none';
  });

  // 内容位置
  document.getElementById('contentPositionType').addEventListener('change', function() {
    document.getElementById('fixedOffsetGroup').style.display = this.value === 'fixed' ? 'block' : 'none';
  });

  // 十六进制输入验证
  ['rangeStart', 'rangeEnd'].forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener('input', function() {
        this.value = this.value.replace(/[^0-9A-Fa-f]/g, '').toUpperCase();
        generateCommands();
      });
    }
  });

  // 所有输入变化时更新命令
  document.querySelectorAll('input, select').forEach(el => {
    el.addEventListener('change', generateCommands);
    el.addEventListener('input', generateCommands);
  });
  
  document.querySelectorAll('.animate-check').forEach(cb => {
    cb.addEventListener('change', generateCommands);
  });
}

// 步骤切换
function toggleStep(element, type) {
  if (type === 'radio') {
    const group = element.dataset.group;
    if (group) {
      document.querySelectorAll(`[data-group="${group}"]`).forEach(card => {
        card.classList.remove('selected');
      });
    }
    element.classList.add('selected');
    
    // 显示对应的扩展选项
    const step = element.dataset.step;
    document.querySelectorAll('.extended-options').forEach(opt => opt.style.display = 'none');
    if (step === 'extract') {
      document.getElementById('extractOptions').style.display = 'block';
    } else if (step === 'generate-range') {
      document.getElementById('rangeOptions').style.display = 'block';
    }
  } else {
    element.classList.toggle('selected');
  }
  
  generateCommands();
}

// PNG 选项选择
function selectPngOption(element, group) {
  document.querySelectorAll(`[data-png-option="${group}"]`).forEach(card => {
    card.classList.remove('selected');
  });
  element.classList.add('selected');
  pngOptions.bgMode = element.dataset.value;
  
  document.getElementById('rainbowConfig').style.display = 
    pngOptions.bgMode === 'rainbow' ? 'block' : 'none';
  
  generateCommands();
}

// 字体文件处理
function handleFontFiles(input) {
  const files = input.files;
  for (let i = 0; i < files.length; i++) {
    const file = files[i];
    if (!fontList.includes(file.name)) {
      fontList.push(file.name);
    }
  }
  updateFontList();
  generateCommands();
}

function updateFontList() {
  const container = document.getElementById('fontList');
  
  if (fontList.length === 0) {
    container.innerHTML = '<div class="empty-list">点击下方按钮选择字体文件</div>';
    return;
  }
  
  container.innerHTML = '';
  fontList.forEach((font, index) => {
    const item = document.createElement('div');
    item.className = 'font-item';
    item.innerHTML = `
      <span class="font-name">${font}</span>
      <div class="font-controls">
        <button class="font-btn" onclick="moveFontUp(${index})" ${index === 0 ? 'disabled' : ''}>↑</button>
        <button class="font-btn" onclick="moveFontDown(${index})" ${index === fontList.length - 1 ? 'disabled' : ''}>↓</button>
        <button class="font-btn" onclick="removeFont(${index})" style="background:#da3633;">✕</button>
      </div>
    `;
    container.appendChild(item);
  });
}

function moveFontUp(index) {
  if (index > 0) {
    [fontList[index], fontList[index - 1]] = [fontList[index - 1], fontList[index]];
    updateFontList();
    generateCommands();
  }
}

function moveFontDown(index) {
  if (index < fontList.length - 1) {
    [fontList[index], fontList[index + 1]] = [fontList[index + 1], fontList[index]];
    updateFontList();
    generateCommands();
  }
}

function removeFont(index) {
  fontList.splice(index, 1);
  updateFontList();
  generateCommands();
}

// 转圈预设
function setSpinnerPreset(type) {
  const presets = {
    'line': '-,/,|,\\',
    'circle': '◐,◓,◑,◒',
    'braille': '⣾,⣽,⣻,⢿,⡿,⣟,⣯,⣷',
    'arrow': '←,↖,↑,↗,→,↘,↓,↙'
  };
  document.getElementById('spinnerStrings').value = presets[type] || '';
  generateCommands();
}

// 清空所有选择
function clearAll() {
  document.querySelectorAll('.step-card').forEach(card => {
    card.classList.remove('selected');
  });
  
  document.querySelectorAll('.extended-options').forEach(opt => opt.style.display = 'none');
  
  fontList = [];
  updateFontList();
  
  // 重置 PNG 选项
  document.querySelector('[data-png-option="bg-mode"][data-value="dynamic"]').classList.add('selected');
  document.querySelector('[data-png-option="bg-mode"][data-value="fixed"]')?.classList.remove('selected');
  document.querySelector('[data-png-option="bg-mode"][data-value="random"]')?.classList.remove('selected');
  document.querySelector('[data-png-option="bg-mode"][data-value="rainbow"]')?.classList.remove('selected');
  
  document.querySelectorAll('.animate-check').forEach(cb => cb.checked = false);
  document.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = false);
  
  generateCommands();
}

// 切换所有区块折叠
function toggleAllSections() {
  const sections = document.querySelectorAll('.section');
  const allCollapsed = Array.from(sections).every(s => s.classList.contains('collapsed'));
  
  sections.forEach(s => {
    if (allCollapsed) {
      s.classList.remove('collapsed');
    } else {
      s.classList.add('collapsed');
    }
  });
}

// 更新 UI
function updateUI() {
  // 从 DOM 读取所有 PNG 选项
  pngOptions.gradientCycle = document.getElementById('gradientCycle').value;
  pngOptions.gradientType = document.getElementById('gradientType').value;
  pngOptions.gradientColors = document.getElementById('gradientColors').value;
  
  pngOptions.animateElements = [];
  document.querySelectorAll('.animate-check:checked').forEach(cb => {
    pngOptions.animateElements.push(cb.value);
  });
  
  pngOptions.animationType = document.getElementById('animationType').value;
  pngOptions.animationAmplitude = document.getElementById('animationAmplitude').value;
  pngOptions.movementSpeed = document.getElementById('movementSpeed').value;
  pngOptions.animationSpeed = document.getElementById('animationSpeed').value;
  
  pngOptions.showEncoding = document.getElementById('showEncoding').checked;
  pngOptions.showBlockPosition = document.getElementById('showBlockPosition').checked;
  pngOptions.showGlobalPosition = document.getElementById('showGlobalPosition').checked;
  pngOptions.showBlockProgressBar = document.getElementById('showBlockProgressBar').checked;
  pngOptions.showGlobalProgressBar = document.getElementById('showGlobalProgressBar').checked;
  pngOptions.showNamesInfo = document.getElementById('showNamesInfo').checked;
  pngOptions.showSideSpinner = document.getElementById('showSideSpinner').checked;
  pngOptions.disableCombOverlay = document.getElementById('disableCombOverlay').checked;
  
  pngOptions.spinnerStrings = document.getElementById('spinnerStrings').value;
  pngOptions.spinnerStepInterval = document.getElementById('spinnerStepInterval').value;
  
  pngOptions.contentPositionType = document.getElementById('contentPositionType').value;
  pngOptions.contentOffsetX = document.getElementById('contentOffsetX').value;
  pngOptions.contentOffsetY = document.getElementById('contentOffsetY').value;
  
  pngOptions.scaleFactor = document.getElementById('scaleFactor').value;
  pngOptions.shuffleContent = document.getElementById('shuffleContent').checked;
  pngOptions.workers = document.getElementById('workers').value;
  pngOptions.pngQuality = document.getElementById('pngQuality').value;
  pngOptions.forceRegenerate = document.getElementById('forceRegenerate').checked;
  pngOptions.flashColor = document.getElementById('flashColor').value;
}

// 生成 PNG 命令
function generatePngCommand() {
  updateUI();
  
  let args = [];
  
  // 背景模式
  switch (pngOptions.bgMode) {
    case 'dynamic':
      args.push('--dynamic-bg');
      break;
    case 'random':
      args.push('--random-color');
      break;
    case 'rainbow':
      args.push('--rainbow-gradient');
      args.push(`--gradient-cycle ${pngOptions.gradientCycle}`);
      if (pngOptions.gradientType === 'interpolate') {
        args.push('--no-smooth-gradient');
      }
      if (pngOptions.gradientColors) {
        args.push(`--gradient-colors "${pngOptions.gradientColors}"`);
      }
      break;
  }
  
  // 闪出颜色
  if (pngOptions.flashColor) {
    args.push(`--flash-color "${pngOptions.flashColor}"`);
  }
  
  // 动画
  if (pngOptions.animateElements.length > 0) {
    args.push(`--animate-elements ${pngOptions.animateElements.join(',')}`);
    args.push(`--animation-type ${pngOptions.animationType}`);
    args.push(`--animation-amplitude ${pngOptions.animationAmplitude}`);
    args.push(`--movement-speed ${pngOptions.movementSpeed}`);
    args.push(`--animation-speed ${pngOptions.animationSpeed}`);
  }
  
  // 信息显示
  if (pngOptions.showEncoding) args.push('--show-encoding');
  if (pngOptions.showBlockPosition) args.push('--show-block-position');
  if (pngOptions.showGlobalPosition) args.push('--show-global-position');
  if (pngOptions.showBlockProgressBar) args.push('--show-block-progress-bar');
  if (pngOptions.showGlobalProgressBar) args.push('--show-global-progress-bar');
  if (pngOptions.showNamesInfo) args.push('--show-names-info');
  if (pngOptions.disableCombOverlay) args.push('--disable-comb-overlay');
  
  // 转圈动画
  if (pngOptions.showSideSpinner) {
    args.push('--show-side-spinner');
    args.push(`--spinner-strings "${pngOptions.spinnerStrings}"`);
    args.push(`--spinner-step-interval ${pngOptions.spinnerStepInterval}`);
  }
  
  // 内容位置
  if (pngOptions.contentPositionType === 'random') {
    args.push('--content-position random');
  } else if (pngOptions.contentPositionType === 'fixed') {
    args.push(`--content-position fixed,${pngOptions.contentOffsetX},${pngOptions.contentOffsetY}`);
  }
  
  // 其他
  if (pngOptions.scaleFactor != 1.0) {
    args.push(`--scale ${pngOptions.scaleFactor}`);
  }
  if (pngOptions.shuffleContent) {
    args.push('--shuffle-content');
  }
  if (pngOptions.forceRegenerate) {
    args.push('--force');
  }
  
  args.push(`--workers ${pngOptions.workers}`);
  args.push(`--png-quality ${pngOptions.pngQuality}`);
  
  return `.\\python\\python.exe ".\\scripts\\generate_png.py" ${args.join(' ')}`;
}

// 生成完整命令
function generateCommands() {
  updateUI();
  
  const selectedCards = document.querySelectorAll('.step-card.selected');
  const output = document.getElementById('commandOutput');
  
  if (selectedCards.length === 0) {
    output.textContent = '# 请选择要执行的步骤';
    return;
  }
  
  let commands = [];
  commands.push('# ========================================');
  commands.push('# Unicode Flash Mob 命令序列');
  commands.push('# 生成时间: ' + new Date().toLocaleString('zh-CN'));
  commands.push('# ========================================');
  commands.push('');
  
  // 按步骤分组
  const stepOrder = ['download', 'write-settings', 'process-block', 'process-data', 
                     'extract', 'generate-range', 'rename', 'replace', 
                     'generate-png', 'generate-mp4', 'open-output', 'cleanup'];
  
  const selectedSteps = Array.from(selectedCards).map(card => card.dataset.step);
  
  stepOrder.forEach(step => {
    if (!selectedSteps.includes(step)) return;
    
    const card = document.querySelector(`[data-step="${step}"]`);
    if (!card) return;
    
    const title = card.querySelector('.step-title')?.textContent || step;
    commands.push(`# ${title}`);
    commands.push('# ' + '-'.repeat(40));
    
    let cmd = '';
    switch (step) {
      case 'download':
        cmd = './unicode_flash_mob.exe download';
        break;
      case 'write-settings':
        cmd = './unicode_flash_mob.exe write-settings';
        break;
      case 'process-block':
        cmd = './unicode_flash_mob.exe process-unicode-block';
        break;
      case 'process-data':
        cmd = './unicode_flash_mob.exe process-unicode-data';
        break;
      case 'extract':
        if (fontList.length > 0) {
          const outFile = document.getElementById('extractOutFile')?.value || 'combined_unicode_list.txt';
          const fonts = fontList.map(f => `"${f}"`).join(' ');
          const mode = document.getElementById('extractMode')?.value || 'any';
          const style = document.getElementById('extractStyle')?.value || 'fallback';
          cmd = `./unicode_flash_mob.exe extract ${fonts} --out "${outFile}" --mode ${mode} --style ${style}`;
        } else {
          cmd = './unicode_flash_mob.exe extract [请选择字体文件]';
        }
        break;
      case 'generate-range':
        const start = document.getElementById('rangeStart').value || '0000';
        const end = document.getElementById('rangeEnd').value || '10FFFF';
        const outFile = document.getElementById('rangeOutFile').value || 'combined_unicode_list.txt';
        const fontPath = document.getElementById('rangeFontPath').value || 'font.ttf';
        cmd = `./unicode_flash_mob.exe generate-unicode-range --file "${outFile}" --start ${start} --end ${end} --font "${fontPath}"`;
        break;
      case 'rename':
        cmd = 'Rename-Item \'combined_unicode_list.txt\' \'Unicode.txt\' -ErrorAction Stop';
        break;
      case 'replace':
        const replaceCard = document.querySelector('[data-step="replace"].selected');
        const mode = replaceCard ? replaceCard.querySelector('.step-command').textContent.match(/\d+/)[0] : '3';
        cmd = `./unicode_flash_mob.exe replace-unicode-data ${mode}`;
        break;
      case 'generate-png':
        cmd = generatePngCommand();
        document.querySelector('#pngCommand').textContent = cmd;
        break;
      case 'generate-mp4':
        cmd = '.\\python\\python.exe ".\\scripts\\generate_mp4.py"';
        break;
      case 'open-output':
        cmd = 'Start-Process .\\output';
        break;
      case 'cleanup':
        cmd = 'Remove-Item "Unicode.txt","color_state.json" -Force -ErrorAction SilentlyContinue';
        break;
    }
    
    commands.push(cmd);
    commands.push('');
  });
  
  commands.push('# ========================================');
  commands.push('Write-Host "所有选定步骤已完成" -ForegroundColor Green');
  
  output.textContent = commands.join('\n');
}

// 复制到剪贴板
function copyToClipboard() {
  const output = document.getElementById('commandOutput');
  navigator.clipboard.writeText(output.textContent).then(() => {
    showCopyFeedback();
  }).catch(() => {
    const textArea = document.createElement('textarea');
    textArea.value = output.textContent;
    document.body.appendChild(textArea);
    textArea.select();
    document.execCommand('copy');
    document.body.removeChild(textArea);
    showCopyFeedback();
  });
}

function showCopyFeedback() {
  const btn = document.querySelector('.copy-btn');
  const originalText = btn.innerHTML;
  btn.innerHTML = '✅ 已复制!';
  btn.style.background = '#238636';
  
  setTimeout(() => {
    btn.innerHTML = originalText;
    btn.style.background = '#30363d';
  }, 2000);
}