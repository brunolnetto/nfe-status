using Xunit;
using NfeStatusCSharp;
using Microsoft.Extensions.Logging.Abstractions;

public class NfeStatusTests
{
    [Fact]
    public void Config_Loads_Defaults()
    {
        var config = NfeConfig.LoadFromEnvironment();
        Assert.NotNull(config);
        Assert.Equal("https://www.nfe.fazenda.gov.br/portal/disponibilidade.aspx", config.Url);
        Assert.Equal("disponibilidade.db", config.DbPath);
    }

    [Fact]
    public void ParseNfeStatusHtml_Returns_Empty_On_InvalidHtml()
    {
        var logger = NullLogger.Instance;
        var result = Program.ParseNfeStatusHtml("<html><body>No table here</body></html>", logger);
        Assert.False(result.Success);
        Assert.NotNull(result.ErrorMessage);
    }

    [Fact]
    public void ParseNfeStatusHtml_Parses_ValidTable()
    {
        var logger = NullLogger.Instance;
        string html = @"<table id='ctl00_ContentPlaceHolder1_gdvDisponibilidade2'>
            <tr><th>Autorizador</th><th>Status</th></tr>
            <tr><td>SVAN</td><td>verde</td></tr>
            <tr><td>SVRS</td><td>amarelo</td></tr>
        </table>";
        var result = Program.ParseNfeStatusHtml(html, logger);
        Assert.True(result.Success);
        Assert.Equal(2, result.Statuses.Count);
        Assert.Equal("SVAN", result.Statuses[0]["autorizador"]);
        Assert.Equal("amarelo", result.Statuses[1]["status"]);
    }
}