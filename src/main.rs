mod downloader;
mod settings_writer;
mod process_unicodeblock;
mod process_unicodedata;
mod font_unicode_decipher;
mod unicode_range_generator;

use anyhow::Result;
use clap::{Parser, Subcommand};
use std::path::PathBuf;
use font_unicode_decipher::{ExtractMode, FontStyle};

#[derive(Parser)]
#[command(author, version, about = "Unicode 工具集")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    Download,
    WriteSettings,
    ProcessUnicodeBlock,
    ProcessUnicodeData,
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
    GenerateUnicodeRange {
        #[arg(short, long, value_name = "FILENAME")]
        file: String,
        #[arg(short, long, value_name = "START_HEX")]
        start: String,
        #[arg(short, long, value_name = "END_HEX")]
        end: String,
        #[arg(short, long, value_name = "FONT_PATH")]
        font: Option<String>,
    },
    ReplaceUnicodeData {
        #[arg(value_name = "MODE")]
        mode: Option<u8>,
    },
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    match cli.command {
        Commands::Download => downloader::main()?,
        Commands::WriteSettings => settings_writer::main()?,
        Commands::ProcessUnicodeBlock => process_unicodeblock::main()?,
        Commands::ProcessUnicodeData => process_unicodedata::main()?,
        Commands::Extract { font_files, out, mode, style } => {
            let extract_mode = ExtractMode::from_str(&mode)?;
            let font_style = FontStyle::from_str(&style)?;
            font_unicode_decipher::extract_unicode_from_fonts(&font_files, out.as_deref(), extract_mode, font_style)?
        }
        Commands::GenerateUnicodeRange {
            file,
            start,
            end,
            font,
        } => {
            unicode_range_generator::write_to_file(&file, &start, &end, font.as_deref())?
        }
        Commands::ReplaceUnicodeData { mode } => {
            font_unicode_decipher::replace_unicode(mode)?
        }
    }
    Ok(())
}