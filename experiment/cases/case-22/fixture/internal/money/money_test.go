package money

import "testing"

func TestParse(t *testing.T) {
	cases := []struct {
		in, cur string
		want    Minor
		err     bool
	}{
		{"12.50", "USD", 1250, false},
		{"0.1", "USD", 10, false},
		{"1500", "JPY", 1500, false},
		{"1.5", "JPY", 0, true},
		{"12.345", "USD", 0, true},
		{"3.141", "KWD", 3141, false},
		{"abc", "USD", 0, true},
		{"1.00", "XXX", 0, true},
	}
	for _, c := range cases {
		got, err := Parse(c.in, c.cur)
		if (err != nil) != c.err || got != c.want {
			t.Errorf("Parse(%q,%q) = %d, %v", c.in, c.cur, got, err)
		}
	}
}
