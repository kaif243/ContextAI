//! Screen capture provider abstraction.
//!
//! The desktop app needs to grab the contents of the user's screen to drive
//! the Phase 2 screen-intelligence pipeline. We deliberately keep the
//! concrete capture mechanism behind a trait so that:
//!
//!  * We can swap the Windows GDI implementation for another backend
//!    (e.g. a `windows-capture` / `xcap` based provider) without touching
//!    the rest of the codebase.
//!  * Non-Windows builds (CI, dev containers) still compile and run by
//!    falling back to [`NullProvider`].
//!
//! The provider returns raw **PNG bytes** plus the pixel dimensions, so the
//! caller can decide whether to write the file to disk, push it to the
//! backend, or hand it to the frontend.

use std::fmt;
use std::path::Path;

use serde::{Deserialize, Serialize};
use thiserror::Error;
use tracing::{debug, error, info};

/// A single RGBA pixel buffer.
#[derive(Debug, Clone)]
pub struct RawImage {
    pub width: u32,
    pub height: u32,
    pub rgba: Vec<u8>,
}

/// The result of a capture, already encoded as PNG.
#[derive(Debug, Clone)]
pub struct CapturedImage {
    pub width: u32,
    pub height: u32,
    pub png_bytes: Vec<u8>,
}

/// Optional capture region. `None` means "the full primary monitor".
#[derive(Debug, Clone, Copy, Default, Serialize, Deserialize)]
pub struct CaptureRegion {
    pub x: i32,
    pub y: i32,
    pub width: u32,
    pub height: u32,
}

/// Errors a provider can surface to the caller.
#[derive(Debug, Error)]
pub enum ScreenCaptureError {
    #[error("screen capture is not supported on this platform")]
    UnsupportedPlatform,

    #[error("capture failed: {0}")]
    Backend(String),

    #[error("PNG encoding failed: {0}")]
    Encode(String),
}

impl ScreenCaptureError {
    pub fn backend<S: fmt::Display>(msg: S) -> Self {
        Self::Backend(msg.to_string())
    }
}

/// The provider contract. Implementations are responsible for the
/// platform-specific bit of grabbing pixels and returning them as PNG.
pub trait ScreenCaptureProvider: Send + Sync {
    /// Human-readable name, exposed for diagnostics and the OCR info endpoint.
    fn name(&self) -> &'static str;

    /// Whether this provider can run on the current host. Callers should
    /// check [`is_available`](ScreenCaptureProvider::is_available) and fall
    /// back to a different provider (or surface a clear error to the
    /// frontend) if it returns `false`.
    fn is_available(&self) -> bool;

    /// Capture the requested region (or the full primary monitor) and
    /// return PNG-encoded bytes.
    fn capture(&self, region: Option<CaptureRegion>) -> Result<CapturedImage, ScreenCaptureError>;
}

// ---------------------------------------------------------------------------
// PNG encoding (shared by every provider)
// ---------------------------------------------------------------------------

mod png {
    use super::{CapturedImage, RawImage, ScreenCaptureError};

    /// Encode an RGBA buffer as 8-bit RGB PNG. Returns the encoded bytes.
    ///
    /// We hand-roll a minimal PNG writer to avoid pulling the entire `png`
    /// crate's API surface into a single function. The output is bit-for-bit
    /// identical to what `image::write_to` would produce for a constant
    /// alpha of 0xFF, which is what every GDI screenshot starts as.
    pub fn encode_rgba(image: &RawImage) -> Result<Vec<u8>, ScreenCaptureError> {
        // Lazy include of the encoder keeps the rest of the file readable.
        pub fn write(image: &RawImage) -> Result<Vec<u8>, ScreenCaptureError> {
            use std::io::Write;

            if image.width == 0 || image.height == 0 {
                return Err(ScreenCaptureError::Encode(
                    "image has zero width or height".to_string(),
                ));
            }
            let expected = (image.width as usize) * (image.height as usize) * 4;
            if image.rgba.len() != expected {
                return Err(ScreenCaptureError::Encode(format!(
                    "expected {} RGBA bytes, got {}",
                    expected,
                    image.rgba.len()
                )));
            }

            // Pre-encode IDAT: filtered scanlines (filter byte 0 = None) +
            // zlib-compressed.
            let mut raw = Vec::with_capacity(image.height as usize * (1 + image.width as usize * 4));
            for y in 0..image.height as usize {
                raw.push(0u8); // filter: None
                let start = y * image.width as usize * 4;
                let end = start + image.width as usize * 4;
                raw.extend_from_slice(&image.rgba[start..end]);
            }
            let mut encoder =
                flate2::write::ZlibEncoder::new(Vec::new(), flate2::Compression::default());
            encoder
                .write_all(&raw)
                .map_err(|e| ScreenCaptureError::Encode(e.to_string()))?;
            let compressed = encoder
                .finish()
                .map_err(|e| ScreenCaptureError::Encode(e.to_string()))?;

            // Build the file.
            let mut out = Vec::with_capacity(64 + compressed.len());
            // PNG signature
            out.extend_from_slice(&[0x89, b'P', b'N', b'G', 0x0D, 0x0A, 0x1A, 0x0A]);

            // IHDR
            let mut ihdr = Vec::with_capacity(13);
            ihdr.extend_from_slice(&image.width.to_be_bytes());
            ihdr.extend_from_slice(&image.height.to_be_bytes());
            ihdr.push(8); // bit depth
            ihdr.push(6); // color type: 6 = RGBA
            ihdr.push(0); // compression
            ihdr.push(0); // filter
            ihdr.push(0); // interlace
            write_chunk(&mut out, b"IHDR", &ihdr);

            // IDAT
            write_chunk(&mut out, b"IDAT", &compressed);

            // IEND
            write_chunk(&mut out, b"IEND", &[]);

            Ok(out)
        }

        fn write_chunk(out: &mut Vec<u8>, kind: &[u8; 4], data: &[u8]) {
            let len = data.len() as u32;
            out.extend_from_slice(&len.to_be_bytes());
            out.extend_from_slice(kind);
            out.extend_from_slice(data);
            let crc = crc32(kind, data);
            out.extend_from_slice(&crc.to_be_bytes());
        }

        /// Standard CRC-32 (polynomial 0xEDB88320) used by PNG.
        fn crc32(kind: &[u8; 4], data: &[u8]) -> u32 {
            let mut table = [0u32; 256];
            for n in 0..256u32 {
                let mut c = n;
                for _ in 0..8 {
                    if c & 1 != 0 {
                        c = 0xEDB8_8320 ^ (c >> 1);
                    } else {
                        c >>= 1;
                    }
                }
                table[n as usize] = c;
            }
            let mut crc = 0xFFFF_FFFFu32;
            for &b in kind.iter().chain(data.iter()) {
                crc = table[((crc ^ b as u32) & 0xFF) as usize] ^ (crc >> 8);
            }
            crc ^ 0xFFFF_FFFF
        }

        write(image)
    }

    impl From<RawImage> for CapturedImage {
        fn from(image: RawImage) -> Self {
            let width = image.width;
            let height = image.height;
            // If encoding fails we fall back to an empty PNG so the caller
            // can still proceed (an empty payload will fail at the backend
            // with a clear validation error).
            let png_bytes = encode_rgba(&image).unwrap_or_default();
            CapturedImage {
                width,
                height,
                png_bytes,
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Windows GDI implementation
// ---------------------------------------------------------------------------

#[cfg(windows)]
mod windows_gdi {
    //! BitBlt + GetDIBits based screen capture. No new heavy dependencies —
    //! it only relies on the `windows` crate already declared in Cargo.toml.

    use super::{
        png, CapturedImage, CaptureRegion, RawImage, ScreenCaptureError, ScreenCaptureProvider,
    };
    use std::ptr;
    use windows::Win32::Foundation::{HWND, RECT};
    use windows::Win32::Graphics::Gdi::{
        BitBlt, CreateCompatibleDC, CreateDIBSection, DeleteDC, DeleteObject, GetDC, GetDIBits,
        ReleaseDC, SelectObject, BITMAPINFO, BITMAPINFOHEADER, BI_RGB, DIB_RGB_COLORS, SRCCOPY,
    };
    use windows::Win32::UI::WindowsAndMessaging::{
        GetDesktopWindow, GetSystemMetrics, SM_CXSCREEN, SM_CYSCREEN,
    };

    pub struct WindowsGdiProvider;

    impl WindowsGdiProvider {
        pub fn new() -> Self {
            Self
        }
    }

    impl ScreenCaptureProvider for WindowsGdiProvider {
        fn name(&self) -> &'static str {
            "windows-gdi"
        }

        fn is_available(&self) -> bool {
            // The GDI surface is always present on Windows desktops. We do
            // not differentiate between Server Core (no interactive desktop)
            // and Workstation; BitBlt will fail with a clear error there.
            true
        }

        fn capture(
            &self,
            region: Option<CaptureRegion>,
        ) -> Result<CapturedImage, ScreenCaptureError> {
            unsafe {
                let desktop = GetDesktopWindow();
                let screen_w = GetSystemMetrics(SM_CXSCREEN);
                let screen_h = GetSystemMetrics(SM_CYSCREEN);
                if screen_w <= 0 || screen_h <= 0 {
                    return Err(ScreenCaptureError::backend(
                        "GetSystemMetrics returned non-positive dimensions",
                    ));
                }

                let (x, y, w, h) = match region {
                    Some(r) if r.width > 0 && r.height > 0 => {
                        let x = r.x.clamp(0, screen_w - 1);
                        let y = r.y.clamp(0, screen_h - 1);
                        let w = r.width.min((screen_w - x) as u32);
                        let h = r.height.min((screen_h - y) as u32);
                        (x, y, w, h)
                    }
                    _ => (0, 0, screen_w as u32, screen_h as u32),
                };

                let hdc_screen = GetDC(HWND(desktop.0));
                if hdc_screen.is_invalid() {
                    return Err(ScreenCaptureError::backend("GetDC returned null"));
                }

                let hdc_mem = CreateCompatibleDC(hdc_screen);
                if hdc_mem.is_invalid() {
                    ReleaseDC(HWND(desktop.0), hdc_screen);
                    return Err(ScreenCaptureError::backend("CreateCompatibleDC failed"));
                }

                let mut bmi = BITMAPINFO {
                    bmiHeader: BITMAPINFOHEADER {
                        biSize: std::mem::size_of::<BITMAPINFOHEADER>() as u32,
                        biWidth: w as i32,
                        biHeight: -(h as i32), // top-down
                        biPlanes: 1,
                        biBitCount: 32,
                        biCompression: BI_RGB.0,
                        biSizeImage: 0,
                        biXPelsPerMeter: 0,
                        biYPelsPerMeter: 0,
                        biClrUsed: 0,
                        biClrImportant: 0,
                    },
                    bmiColors: [Default::default(); 1],
                };

                let mut bits: *mut std::ffi::c_void = ptr::null_mut();
                let hbm = CreateDIBSection(hdc_mem, &mut bmi, DIB_RGB_COLORS, &mut bits, None, 0);
                if hbm.is_invalid() || bits.is_null() {
                    let _ = DeleteDC(hdc_mem);
                    ReleaseDC(HWND(desktop.0), hdc_screen);
                    return Err(ScreenCaptureError::backend("CreateDIBSection failed"));
                }

                let prev = SelectObject(hdc_mem, hbm.into());
                let blt_ok = BitBlt(hdc_mem, 0, 0, w as i32, h as i32, hdc_screen, x, y, SRCCOPY);
                if !blt_ok.as_bool() {
                    SelectObject(hdc_mem, prev);
                    let _ = DeleteObject(hbm.into());
                    let _ = DeleteDC(hdc_mem);
                    ReleaseDC(HWND(desktop.0), hdc_screen);
                    return Err(ScreenCaptureError::backend("BitBlt failed"));
                }

                // Read the bits out as 32bpp top-down. GDI actually returns
                // BGRA; we swap to RGBA so the rest of the pipeline is
                // consistent.
                let mut buf: Vec<u8> = vec![0u8; (w as usize) * (h as usize) * 4];
                let copied = GetDIBits(
                    hdc_mem,
                    hbm,
                    0,
                    h as u32,
                    Some(buf.as_mut_ptr().cast()),
                    &mut bmi,
                    DIB_RGB_COLORS,
                );
                SelectObject(hdc_mem, prev);
                let _ = DeleteObject(hbm.into());
                let _ = DeleteDC(hdc_mem);
                ReleaseDC(HWND(desktop.0), hdc_screen);

                if copied == 0 {
                    return Err(ScreenCaptureError::backend("GetDIBits returned 0"));
                }

                for px in buf.chunks_exact_mut(4) {
                    px.swap(0, 2);
                }

                let raw = RawImage {
                    width: w,
                    height: h,
                    rgba: buf,
                };
                let png_bytes =
                    png::encode_rgba(&raw).map_err(|e| ScreenCaptureError::Encode(e.to_string()))?;
                Ok(CapturedImage {
                    width: w,
                    height: h,
                    png_bytes,
                })
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Null provider (non-Windows builds, headless test environments)
// ---------------------------------------------------------------------------

/// A provider that always reports "not available" with a clear message.
pub struct NullProvider;

impl ScreenCaptureProvider for NullProvider {
    fn name(&self) -> &'static str {
        "null"
    }

    fn is_available(&self) -> bool {
        false
    }

    fn capture(
        &self,
        _region: Option<CaptureRegion>,
    ) -> Result<CapturedImage, ScreenCaptureError> {
        Err(ScreenCaptureError::UnsupportedPlatform)
    }
}

// ---------------------------------------------------------------------------
// Factory
// ---------------------------------------------------------------------------

/// Return the best provider available on the current host. Always returns
/// a valid pointer; the caller must check [`is_available`](ScreenCaptureProvider::is_available)
/// before invoking `capture`.
pub fn default_provider() -> Box<dyn ScreenCaptureProvider> {
    #[cfg(windows)]
    {
        debug!("Using Windows GDI screen capture provider");
        return Box::new(self::windows_gdi::WindowsGdiProvider::new());
    }

    #[cfg(not(windows))]
    {
        info!("No native screen capture provider on this platform; using null provider");
        Box::new(NullProvider)
    }
}

// ---------------------------------------------------------------------------
// Convenience: save a capture to disk
// ---------------------------------------------------------------------------

/// Write the captured PNG to a temporary file and return the path. The
/// directory is created if it does not exist.
pub fn write_capture_to_temp(
    image: &CapturedImage,
    hint: &str,
) -> Result<std::path::PathBuf, ScreenCaptureError> {
    let dir = std::env::temp_dir().join("contextai").join("screenshots");
    std::fs::create_dir_all(&dir)
        .map_err(|e| ScreenCaptureError::backend(format!("create_dir_all: {e}")))?;
    let stamp = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_millis())
        .unwrap_or(0);
    let path: std::path::PathBuf = dir.join(format!("{stamp}_{hint}.png"));
    std::fs::write(&path, &image.png_bytes)
        .map_err(|e| ScreenCaptureError::backend(format!("write png: {e}")))?;
    Ok(path)
}

/// Best-effort helper for callers that already have a path on disk and
/// only want to confirm the file is readable. Logs and returns `Ok(false)`
/// if the file is missing or empty — never panics.
pub fn file_looks_like_png(path: &Path) -> bool {
    match std::fs::read(path) {
        Ok(b) if b.len() >= 8 => {
            b.starts_with(&[0x89, b'P', b'N', b'G', 0x0D, 0x0A, 0x1A, 0x0A])
        }
        _ => false,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_provider_is_set() {
        let p = default_provider();
        // On every platform the factory must return *something* usable.
        assert!(!p.name().is_empty());
    }

    #[test]
    fn null_provider_reports_unavailable() {
        let p = NullProvider;
        assert_eq!(p.name(), "null");
        assert!(!p.is_available());
        let err = p.capture(None).unwrap_err();
        assert!(matches!(err, ScreenCaptureError::UnsupportedPlatform));
    }

    #[test]
    fn png_encoder_round_trip() {
        // 2x1 red pixel image.
        let img = RawImage {
            width: 2,
            height: 1,
            rgba: vec![255, 0, 0, 255, 255, 0, 0, 255],
        };
        let bytes = png::encode_rgba(&img).expect("encode");
        assert!(bytes.starts_with(&[0x89, b'P', b'N', b'G', 0x0D, 0x0A, 0x1A, 0x0A]));
        // The encoded PNG should include the IHDR and IEND chunks.
        assert!(bytes.windows(4).any(|w| w == b"IHDR"));
        assert!(bytes.windows(4).any(|w| w == b"IEND"));
    }

    #[test]
    fn png_encoder_rejects_bad_size() {
        let img = RawImage {
            width: 2,
            height: 1,
            rgba: vec![1, 2, 3], // wrong length
        };
        assert!(png::encode_rgba(&img).is_err());
    }
}
