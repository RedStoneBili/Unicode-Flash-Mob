use anyhow::{bail, Context, Result};
use clap::{Parser, Subcommand};
use regex::Regex;
use std::{
    collections::{HashMap, HashSet},
    fs,
    fs::File,
    io::{self, BufRead, BufReader, BufWriter, Write},
    path::{PathBuf, Path},
};
use ttf_parser::Face;

const BLOCKS_FILE: &str = "DecipherUnicodeBlocks.txt";
const DATA_FILE: &str = "DecipherUnicodeData.txt";
const TEMP_FILE: &str = "Unicode.txt";

#[derive(Parser)]
#[command(author, version, about = "集成字体 Unicode 提取与说明文件替换工具")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    Extract {
        #[arg(value_name = "FONT_FILES", required = true)]
        font_files: Vec<String>,

        #[arg(short, long, value_name = "OUT_FILE")]
        out: Option<PathBuf>,

        #[arg(long, value_name = "MODE", default_value = "any")]
        mode: String,

        #[arg(long, value_name = "STYLE", default_value = "fallback")]
        style: String,
    },
    Replace {
        #[arg(value_name = "MODE")]
        mode: Option<u8>,
    },
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum ExtractMode {
    Any,
    All,
}

impl ExtractMode {
    pub fn from_str(s: &str) -> Result<Self> {
        match s.to_lowercase().as_str() {
            "any" => Ok(ExtractMode::Any),
            "all" => Ok(ExtractMode::All),
            _ => bail!("无效模式：{}，仅支持 any 或 all", s),
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum FontStyle {
    Fallback,
    Compare,
}

impl FontStyle {
    pub fn from_str(s: &str) -> Result<Self> {
        match s.to_lowercase().as_str() {
            "fallback" => Ok(FontStyle::Fallback),
            "compare" => Ok(FontStyle::Compare),
            _ => bail!("无效样式：{}，仅支持 fallback 或 compare", s),
        }
    }
}

#[allow(dead_code)]
struct FontInfo {
    path: PathBuf,
    face: Face<'static>,
    data: Vec<u8>,
    supported: HashSet<u32>,
}

impl FontInfo {
    fn load(path: &Path) -> Result<Self> {
        let data = fs::read(path)
            .with_context(|| format!("无法读取字体文件：{:?}", path))?;

        let data_leaked = Box::leak(data.clone().into_boxed_slice());
        let face = Face::parse(data_leaked, 0)
            .with_context(|| format!("解析字体失败（{:?} 不是有效的 TTF/OTF）", path))?;

        let mut supported = HashSet::new();
        for cp in 0..=0x10FFFF {
            if let Some(ch) = std::char::from_u32(cp) {
                if face.glyph_index(ch).is_some() {
                    supported.insert(cp);
                }
            }
        }

        Ok(FontInfo {
            path: path.to_path_buf(),
            face,
            data,
            supported,
        })
    }

    fn supports(&self, cp: u32) -> bool {
        self.supported.contains(&cp)
    }

    fn name(&self) -> String {
        self.path.file_name()
            .map(|n| n.to_string_lossy().to_string())
            .unwrap_or_else(|| self.path.to_string_lossy().to_string())
    }
}

fn collect_all_font_paths(specs: &[String]) -> Vec<String> {
    let mut paths = Vec::new();
    for spec in specs {
        if spec.starts_with('(') && spec.ends_with(')') {
            let inner = &spec[1..spec.len()-1];
            for name in inner.split(',').map(|s| s.trim()) {
                if !name.is_empty() {
                    paths.push(name.to_string());
                }
            }
        } else {
            paths.push(spec.clone());
        }
    }
    paths
}

fn parse_slot_spec(spec: &str, loaded_fonts: &HashMap<String, FontInfo>) -> Vec<FontInfo> {
    if spec.starts_with('(') && spec.ends_with(')') {
        let inner = &spec[1..spec.len()-1];
        let mut result = Vec::new();
        for name in inner.split(',').map(|s| s.trim()) {
            if let Some(font) = loaded_fonts.get(name) {
                result.push(FontInfo {
                    path: font.path.clone(),
                    face: unsafe { std::mem::transmute_copy(&font.face) },
                    data: font.data.clone(),
                    supported: font.supported.clone(),
                });
            }
        }
        result
    } else {
        if let Some(font) = loaded_fonts.get(spec) {
            vec![FontInfo {
                path: font.path.clone(),
                face: unsafe { std::mem::transmute_copy(&font.face) },
                data: font.data.clone(),
                supported: font.supported.clone(),
            }]
        } else {
            Vec::new()
        }
    }
}

fn resolve_slot_font(slot_fonts: &[FontInfo], cp: u32) -> Option<String> {
    for font in slot_fonts {
        if font.supports(cp) {
            return Some(font.name());
        }
    }
    if let Some(first) = slot_fonts.first() {
        Some(first.name())
    } else {
        None
    }
}

pub fn extract_unicode_from_fonts(
    font_specs: &[String],
    out_file: Option<&Path>,
    mode: ExtractMode,
    style: FontStyle,
) -> Result<()> {
    let out_path = out_file
        .map(ToOwned::to_owned)
        .unwrap_or_else(|| PathBuf::from("combined_unicode_list.txt"));

    let all_paths = collect_all_font_paths(font_specs);

    println!("加载字体文件...");
    let mut loaded_fonts: HashMap<String, FontInfo> = HashMap::new();

    for path_str in &all_paths {
        let path = Path::new(path_str);
        match FontInfo::load(path) {
            Ok(info) => {
                let name = info.name();
                println!("  ✓ {} (支持 {} 个字符)", name, info.supported.len());
                let name_clone = name.clone();
                let path_clone = path_str.clone();
                loaded_fonts.insert(name, info);
                if let Some(font_ref) = loaded_fonts.get(&name_clone) {
                    loaded_fonts.insert(path_clone, FontInfo {
                        path: PathBuf::from(path_str),
                        face: unsafe { std::mem::transmute_copy(&font_ref.face) },
                        data: font_ref.data.clone(),
                        supported: font_ref.supported.clone(),
                    });
                }
            }
            Err(e) => {
                eprintln!("  ✗ 加载失败 {}: {}", path_str, e);
            }
        }
    }

    if loaded_fonts.is_empty() {
        bail!("没有成功加载任何字体");
    }

    let slots: Vec<Vec<FontInfo>> = font_specs.iter()
        .map(|spec| parse_slot_spec(spec, &loaded_fonts))
        .collect();

    println!("\n收集字符码位 (模式: {}, 样式: {})...",
        if mode == ExtractMode::Any { "任一字体支持" } else { "全部字体支持" },
        if style == FontStyle::Compare { "对比" } else { "回退" }
    );

    // ---- 优化开始：使用集合运算代替全范围遍历 ----
    // 展平所有字体（按 slot 顺序）
    let all_fonts: Vec<&FontInfo> = slots.iter().flat_map(|slot| slot.iter()).collect();

    let codepoints_set = match mode {
        ExtractMode::Any => {
            // 求并集
            let mut union = HashSet::new();
            for font in &all_fonts {
                union.extend(&font.supported);
            }
            union
        }
        ExtractMode::All => {
            // 求交集
            if all_fonts.is_empty() {
                HashSet::new()
            } else {
                let mut intersection = all_fonts[0].supported.clone();
                for font in &all_fonts[1..] {
                    intersection.retain(|cp| font.supported.contains(cp));
                }
                intersection
            }
        }
    };

    // 排序
    let mut codepoints: Vec<u32> = codepoints_set.into_iter().collect();
    codepoints.sort();

    println!("共收集 {} 个字符", codepoints.len());

    println!("\n写入文件: {}", out_path.display());
    let file = File::create(&out_path)
        .with_context(|| format!("无法创建输出文件：{:?}", out_path))?;
    let mut writer = BufWriter::new(file);

    match style {
        FontStyle::Compare => {
            // 对比模式：逐码位查询每个 slot 的命中字体（保持原有逻辑）
            for &cp in &codepoints {
                let resolved: Vec<String> = slots.iter()
                    .map(|slot| resolve_slot_font(slot, cp).unwrap_or_else(|| "".to_string()))
                    .filter(|s| !s.is_empty())
                    .collect();
                if !resolved.is_empty() {
                    let font_list_str = resolved.join("|");
                    writeln!(writer, "\"{}\";\"U+{:04X}\"", font_list_str, cp)?;
                }
            }
        }
        FontStyle::Fallback => {
            // 回退模式：预先构建码位→字体名称映射（按 slot 顺序）
            let mut cp_to_font = HashMap::new();
            for slot in &slots {
                for font in slot {
                    for &cp in &font.supported {
                        cp_to_font.entry(cp).or_insert_with(|| font.name());
                    }
                }
            }
            for &cp in &codepoints {
                if let Some(name) = cp_to_font.get(&cp) {
                    writeln!(writer, "\"{}\";\"U+{:04X}\"", name, cp)?;
                }
            }
        }
    }

    writer.flush().context("写入缓冲区失败")?;

    println!("完成！");
    Ok(())
}

pub fn replace_unicode(mode: Option<u8>) -> Result<()> {
    let choice = if let Some(m) = mode {
        match m {
            1 => 1,
            2 => 2,
            3 => 3,
            _ => bail!("无效模式：{}，仅支持 1、2 或 3", m),
        }
    } else {
        loop {
            println!(
                "\n请选择生成图片左下角说明文件：\n\
                 [1] 使用 `{}` 各个字符区块\n\
                 [2] 使用 `{}` 每个字符的详细信息\n\
                 [3] 先区块后详细信息（区块|详细）\n\
                 你选择：",
                BLOCKS_FILE, DATA_FILE
            );
            let mut input = String::new();
            io::stdin().read_line(&mut input)?;
            match input.trim() {
                "1" => break 1,
                "2" => break 2,
                "3" => break 3,
                _ => {
                    println!("输入非法，请输入 1、2 或 3。");
                    continue;
                }
            }
        }
    };

    let blocks_map = if choice == 1 || choice == 3 {
        read_unicode_file(BLOCKS_FILE).with_context(|| format!("解析文件 `{}` 失败", BLOCKS_FILE))?
    } else {
        HashMap::new()
    };
    let data_map = if choice == 2 || choice == 3 {
        read_unicode_file(DATA_FILE).with_context(|| format!("解析文件 `{}` 失败", DATA_FILE))?
    } else {
        HashMap::new()
    };

    replace_content(TEMP_FILE, choice, &blocks_map, &data_map)
        .with_context(|| format!("写入文件 `{}` 失败", TEMP_FILE))?;

    println!("替换完成，结果已写入 `{}`", TEMP_FILE);
    Ok(())
}

fn read_unicode_file(path: &str) -> Result<HashMap<String, String>> {
    let f = File::open(path).with_context(|| format!("无法打开文件 `{}`", path))?;
    let reader = BufReader::new(f);
    let mut map = HashMap::new();

    for line in reader.lines() {
        let line = line.context("读取行失败")?;
        let trimmed = line.trim();
        if let Some(pos) = trimmed.find('-') {
            let code = trimmed[..pos].to_string();
            let desc = trimmed[pos + 1..].to_string();
            map.insert(code, desc);
        }
    }
    Ok(map)
}

fn replace_content(
    path: &str,
    choice: u8,
    blocks_map: &HashMap<String, String>,
    data_map: &HashMap<String, String>,
) -> Result<()> {
    let f = fs::File::open(path)?;
    let reader = BufReader::new(f);
    let re = Regex::new(r#""([^"]+)";"(U\+[0-9A-Fa-f]{4,6})""#).unwrap();

    let mut output = Vec::new();
    for line in reader.lines() {
        let line = line?;

        let replaced = if let Some(caps) = re.captures(&line) {
            let fonts = &caps[1];
            let code = &caps[2];
            let block_desc = blocks_map.get(code);
            let data_desc = data_map.get(code);

            match choice {
                1 => {
                    if let Some(b) = block_desc {
                        format!("\"{}\";\"{}\";\"{}\"", fonts, code, b)
                    } else {
                        format!("\"{}\";\"{}\";\"\"", fonts, code)
                    }
                }
                2 => {
                    if let Some(d) = data_desc {
                        format!("\"{}\";\"{}\";\"{}\"", fonts, code, d)
                    } else {
                        format!("\"{}\";\"{}\";\"\"", fonts, code)
                    }
                }
                3 => {
                    let b = block_desc.map(|s| s.as_str()).unwrap_or("");
                    let d = data_desc.map(|s| s.as_str()).unwrap_or("");
                    if !b.is_empty() || !d.is_empty() {
                        format!("\"{}\";\"{}\";\"{}|{}\"", fonts, code, b, d)
                    } else {
                        format!("\"{}\";\"{}\";\"\"", fonts, code)
                    }
                }
                _ => line.to_string(),
            }
        } else {
            line
        };
        
        output.push(replaced);
    }

    output.sort_by(|a, b| {
        let re_code = Regex::new(r#"U\+([0-9A-Fa-f]{4,6})"#).unwrap();
        let code_a = re_code.captures(a)
            .and_then(|c| c.get(1))
            .and_then(|m| u32::from_str_radix(m.as_str(), 16).ok())
            .unwrap_or(0);
        let code_b = re_code.captures(b)
            .and_then(|c| c.get(1))
            .and_then(|m| u32::from_str_radix(m.as_str(), 16).ok())
            .unwrap_or(0);
        code_a.cmp(&code_b)
    });

    let out_f = fs::File::create(path)?;
    let mut writer = BufWriter::new(out_f);
    for line in output {
        writer.write_all(line.as_bytes())?;
        writer.write_all(b"\n")?;
    }
    writer.flush()?;
    Ok(())
}