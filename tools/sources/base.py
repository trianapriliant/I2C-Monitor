"""
Kontrak untuk sumber data token.

Tiap IDE / AI punya satu file di folder ini. Yang perlu disediakan:

    NAME          -> id untuk --source (huruf kecil, tanpa spasi)
    DISPLAY_NAME  -> nama yang tampil di layar OLED
    class Source(TokenSource)

Selama `poll()` dan `totals()` mengembalikan bentuk yang sama,
token_monitor.py tidak perlu tahu detail IDE-nya sama sekali.
"""


class TokenSource:
    #: id yang dipakai di flag --source
    NAME = "base"
    #: nama yang dikirim ke OLED / ditampilkan di log
    DISPLAY_NAME = "Unknown"

    def __init__(self, scope="today", project=None):
        self.scope = scope
        self.project = project

    def available(self):
        """True kalau sumber datanya memang ada di mesin ini."""
        raise NotImplementedError

    def poll(self):
        """Baca data baru sejak panggilan terakhir. Return jumlah entri baru."""
        raise NotImplementedError

    def totals(self):
        """
        Kembalikan dict dengan kunci:
            input, output, cache_read, cache_write (int)
            cost (float, USD)
            requests (int)
        """
        raise NotImplementedError
