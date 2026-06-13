from django.db import models


class PlatformSettings(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    nome_plataforma = models.CharField(max_length=80, default="FitSync")
    suporte_email = models.EmailField(blank=True, default="")
    cadastro_publico_ativo = models.BooleanField(default=True)
    data_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "platform_settings"
        verbose_name = "configuracao da plataforma"
        verbose_name_plural = "configuracoes da plataforma"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        settings, _ = cls.objects.get_or_create(pk=1)
        return settings

    def __str__(self):
        return self.nome_plataforma
