package media

import (
	"bufio"
	"bytes"
	"errors"
	"fmt"
	"image"
	"image/jpeg"
	_ "image/png"
	"io"
	"net/http"

	"golang.org/x/image/draw"
)

// MaxPixels bounds the pixel count Decode accepts.
var MaxPixels int64

var (
	ErrUnsupportedType = errors.New("unsupported image type")
	ErrTooLarge        = errors.New("image dimensions too large")
)

var allowedTypes = map[string]bool{"image/jpeg": true, "image/png": true}

// Decode sniffs the content type from the bytes (ignoring any client-supplied
// header), checks dimensions before allocating pixel memory, then decodes.
func Decode(r io.Reader) (image.Image, string, error) {
	br := bufio.NewReader(r)
	head, _ := br.Peek(512)
	ct := http.DetectContentType(head)
	if !allowedTypes[ct] {
		return nil, ct, ErrUnsupportedType
	}

	var buf bytes.Buffer
	cfg, _, err := image.DecodeConfig(io.TeeReader(br, &buf))
	if err != nil {
		return nil, ct, fmt.Errorf("read image header: %w", err)
	}
	if int64(cfg.Width)*int64(cfg.Height) > MaxPixels {
		return nil, ct, ErrTooLarge
	}
	img, _, err := image.Decode(io.MultiReader(&buf, br))
	if err != nil {
		return nil, ct, fmt.Errorf("decode image: %w", err)
	}
	return img, ct, nil
}

// SquareJPEG center-crops img to a square and scales it to size x size.
func SquareJPEG(img image.Image, size int, quality int) ([]byte, error) {
	b := img.Bounds()
	side := min(b.Dx(), b.Dy())
	x0 := b.Min.X + (b.Dx()-side)/2
	y0 := b.Min.Y + (b.Dy()-side)/2
	src := image.Rect(x0, y0, x0+side, y0+side)

	dst := image.NewRGBA(image.Rect(0, 0, size, size))
	draw.CatmullRom.Scale(dst, dst.Bounds(), img, src, draw.Over, nil)

	var out bytes.Buffer
	if err := jpeg.Encode(&out, dst, &jpeg.Options{Quality: quality}); err != nil {
		return nil, err
	}
	return out.Bytes(), nil
}
