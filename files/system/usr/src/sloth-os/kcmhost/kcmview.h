#pragma once
// One KDE settings page (KCM) inside a QML scene, the way System Settings shows it: the page and the sub-pages it
// opens ("Modify…", "Configure…") in its own page row, with its header actions. The host gives the Apply / Reset /
// Defaults buttons (save(), load(), defaults()).
#include <QPointer>
#include <QQuickItem>
#include <QtQml/qqmlregistration.h>

class KQuickConfigModule;

class KcmView : public QQuickItem
{
    Q_OBJECT
    QML_ELEMENT
    Q_PROPERTY(QString module READ module WRITE setModule NOTIFY moduleChanged)
    Q_PROPERTY(QStringList arguments READ arguments WRITE setArguments NOTIFY moduleChanged)
    Q_PROPERTY(bool loaded READ loaded NOTIFY stateChanged)
    Q_PROPERTY(QString error READ error NOTIFY stateChanged)
    Q_PROPERTY(QString title READ title NOTIFY stateChanged)
    Q_PROPERTY(bool needsSave READ needsSave NOTIFY stateChanged)
    Q_PROPERTY(bool representsDefaults READ representsDefaults NOTIFY stateChanged)
    Q_PROPERTY(bool instantApply READ instantApply NOTIFY stateChanged)
    Q_PROPERTY(bool hasApply READ hasApply NOTIFY stateChanged)
    Q_PROPERTY(bool hasDefaults READ hasDefaults NOTIFY stateChanged)

public:
    explicit KcmView(QQuickItem *parent = nullptr);
    ~KcmView() override;

    QString module() const { return m_module; }
    void setModule(const QString &module);
    QStringList arguments() const { return m_arguments; }
    void setArguments(const QStringList &arguments);
    bool loaded() const;
    QString error() const { return m_error; }
    QString title() const;
    bool needsSave() const;
    bool representsDefaults() const;
    bool instantApply() const;
    bool hasApply() const;
    bool hasDefaults() const;

    Q_INVOKABLE void save();
    Q_INVOKABLE void reset();
    Q_INVOKABLE void defaults();

Q_SIGNALS:
    void moduleChanged();
    void stateChanged();

protected:
    void componentComplete() override;
    void geometryChange(const QRectF &newGeometry, const QRectF &oldGeometry) override;

private Q_SLOTS:
    void syncCurrentIndex();

private:
    void load();
    void unload();
    void fail(const QString &message);
    void layoutHost();

    QString m_module;
    QStringList m_arguments;
    QString m_error;
    QPointer<KQuickConfigModule> m_kcm;
    QPointer<QQuickItem> m_host;      // a Kirigami.ApplicationItem holding the page row
    QPointer<QQuickItem> m_pageRow;
};
