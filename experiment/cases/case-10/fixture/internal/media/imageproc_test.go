package media

import (
	"bytes"
	"errors"
	"image"
	"image/color"
	"image/png"
	"os"
	"testing"
)

func TestMain(m *testing.M) {
	MaxPixels = 4096 * 4096
	os.Exit(m.Run())
}

func pngOf(t *testing.T, w, h int) []byte {
	t.Helper()
	img := image.NewRGBA(image.Rect(0, 0, w, h))
	img.Set(0, 0, color.RGBA{255, 0, 0, 255})
	var buf bytes.Buffer
	if err := png.Encode(&buf, img); err != nil {
		t.Fatal(err)
	}
	return buf.Bytes()
}

func TestDecodeSniffsType(t *testing.T) {
	_, ct, err := Decode(bytes.NewReader(pngOf(t, 10, 10)))
	if err != nil || ct != "image/png" {
		t.Fatalf("ct=%q err=%v", ct, err)
	}
}

func TestDecodeRejectsNonImage(t *testing.T) {
	_, _, err := Decode(bytes.NewReader([]byte("<html>not an image</html>")))
	if !errors.Is(err, ErrUnsupportedType) {
		t.Fatalf("err = %v", err)
	}
}

func TestDecodeRejectsOversize(t *testing.T) {
	prev := MaxPixels
	MaxPixels = 100
	defer func() { MaxPixels = prev }()
	_, _, err := Decode(bytes.NewReader(pngOf(t, 20, 20)))
	if !errors.Is(err, ErrTooLarge) {
		t.Fatalf("err = %v", err)
	}
}

func TestSquareJPEGSize(t *testing.T) {
	img, _, err := Decode(bytes.NewReader(pngOf(t, 300, 200)))
	if err != nil {
		t.Fatal(err)
	}
	out, err := SquareJPEG(img, 128, 85)
	if err != nil {
		t.Fatal(err)
	}
	cfg, _, err := image.DecodeConfig(bytes.NewReader(out))
	if err != nil || cfg.Width != 128 || cfg.Height != 128 {
		t.Fatalf("cfg=%+v err=%v", cfg, err)
	}
}
